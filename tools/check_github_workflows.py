#!/usr/bin/env python3
"""Validate read-only verification workflow security invariants."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

IMMUTABLE_ACTION_RE = re.compile(r"^[^\s@]+@[0-9a-f]{40}\s+#\s+v\S+$")
USES_RE = re.compile(r"^(?P<indent>\s*)-?\s*uses:\s*(?P<value>.+?)\s*$")


class WorkflowError(RuntimeError):
    """Raised when a workflow violates the bounded verification contract."""


def _permissions_are_read_only(lines: list[str]) -> bool:
    found_top_level = False
    for index, line in enumerate(lines):
        if line.strip() != "permissions:":
            continue
        block_indent = len(line) - len(line.lstrip())
        found_top_level = found_top_level or block_indent == 0
        values: list[str] = []
        for following in lines[index + 1 :]:
            if not following.strip():
                continue
            indent = len(following) - len(following.lstrip())
            if indent <= block_indent:
                break
            if indent == block_indent + 2:
                values.append(following.strip())
        if values != ["contents: read"]:
            return False
    return found_top_level


def _checkout_has_no_persisted_credentials(lines: list[str], index: int) -> bool:
    action_line = lines[index]
    action_indent = len(action_line) - len(action_line.lstrip())
    step_indent = (
        action_indent
        if action_line.lstrip().startswith("- uses:")
        else action_indent - 2
    )
    for following in lines[index + 1 :]:
        if not following.strip():
            continue
        indent = len(following) - len(following.lstrip())
        stripped = following.lstrip()
        if indent <= step_indent and stripped.startswith(("- name:", "- uses:")):
            break
        if stripped == "persist-credentials: false":
            return True
    return False


def validate(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not _permissions_are_read_only(lines):
        raise WorkflowError(f"{path}: top-level permissions must be contents: read")
    if "${{ secrets." in text:
        raise WorkflowError(f"{path}: verification workflow must not reference secrets")

    action_count = 0
    for index, line in enumerate(lines):
        match = USES_RE.match(line)
        if match is None:
            continue
        value = match.group("value")
        if value.startswith("./"):
            continue
        action_count += 1
        if IMMUTABLE_ACTION_RE.fullmatch(value) is None:
            raise WorkflowError(
                f"{path}: mutable or uncommented action reference: {value}"
            )
        if value.startswith(
            "actions/checkout@"
        ) and not _checkout_has_no_persisted_credentials(lines, index):
            raise WorkflowError(
                f"{path}: actions/checkout must set persist-credentials: false"
            )
    if action_count == 0:
        raise WorkflowError(f"{path}: no external action references found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        for path in args.paths:
            validate(path)
    except (OSError, WorkflowError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"GitHub workflow checks passed: {len(args.paths)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
