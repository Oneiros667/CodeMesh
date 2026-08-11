#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")


def slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    return re.sub(r"[\s-]+", "-", value).strip("-")


def markdown_without_fences(text: str) -> str:
    output: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not fenced:
            output.append(line)
    return "\n".join(output)


def anchors(path: Path) -> set[str]:
    result: set[str] = set()
    seen: dict[str, int] = {}
    for line in markdown_without_fences(path.read_text(encoding="utf-8")).splitlines():
        match = HEADING.match(line)
        if match is None:
            continue
        base = slug(match.group(1))
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.add(base if count == 0 else f"{base}-{count}")
    return result


def main() -> int:
    failures = 0
    repository_root = Path(".").resolve()
    files = [
        path
        for path in Path(".").rglob("*.md")
        if not any(
            part in {".git", ".venv", "node_modules", "vendor", "references"}
            for part in path.parts
        )
    ]
    anchor_cache: dict[Path, set[str]] = {}
    for source in files:
        text = markdown_without_fences(source.read_text(encoding="utf-8"))
        for raw in LINK.findall(text):
            target_value = raw.split(maxsplit=1)[0].strip("<>")
            if target_value.startswith(("http://", "https://", "mailto:")):
                continue
            path_value, _, fragment = target_value.partition("#")
            target = source if not path_value else source.parent / unquote(path_value)
            target = target.resolve()
            try:
                target.relative_to(repository_root)
            except ValueError:
                print(
                    f"{source}: link escapes repository: {target_value}",
                    file=sys.stderr,
                )
                failures += 1
                continue
            if not target.exists():
                print(f"{source}: missing link target: {target_value}", file=sys.stderr)
                failures += 1
                continue
            if fragment and target.suffix.lower() == ".md":
                available = anchor_cache.setdefault(target, anchors(target))
                if unquote(fragment).lower() not in available:
                    print(f"{source}: missing anchor: {target_value}", file=sys.stderr)
                    failures += 1
    if failures:
        return 1
    print(f"Validated local links in {len(files)} Markdown file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
