#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


SUBJECT = re.compile(
    r"^(?P<type>[a-z][a-z0-9-]*)(\([a-z0-9][a-z0-9._/-]*\))?"
    r"(?P<breaking>!)?: (?P<summary>\S.*)$"
)


def validate(message: str) -> list[str]:
    lines = message.splitlines()
    if not lines or not lines[0].strip():
        return ["commit subject is empty"]
    subject = lines[0].strip()
    if subject.startswith("Merge ") or subject.startswith("Revert "):
        return []
    match = SUBJECT.fullmatch(subject)
    if match is None:
        return ["subject does not match type(optional-scope): imperative summary"]
    if len(subject) > 100:
        return ["subject exceeds 100 characters"]
    if subject.endswith("."):
        return ["subject must not end with a period"]
    has_footer = any(line.startswith("BREAKING CHANGE: ") for line in lines[1:])
    if bool(match.group("breaking")) != has_footer:
        return ["breaking marker and BREAKING CHANGE footer must appear together"]
    return []


def messages_from_range(value: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "log", "--format=%H%x00%B%x00", value],
        check=True,
        capture_output=True,
    )
    fields = result.stdout.decode("utf-8").split("\x00")
    messages: list[tuple[str, str]] = []
    for index in range(0, len(fields) - 1, 2):
        commit = fields[index].strip()
        message = fields[index + 1].strip()
        if commit:
            messages.append((commit, message))
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--message-file")
    source.add_argument("--message")
    source.add_argument("--range")
    args = parser.parse_args()
    if args.message_file:
        messages = [
            (
                args.message_file,
                Path(args.message_file).read_text(encoding="utf-8"),
            )
        ]
    elif args.message is not None:
        messages = [("message", args.message)]
    else:
        messages = messages_from_range(args.range)
    failures = 0
    for identifier, message in messages:
        for error in validate(message):
            print(f"{identifier}: {error}", file=sys.stderr)
            failures += 1
    if failures:
        return 1
    print(f"Validated {len(messages)} Conventional Commit message(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
