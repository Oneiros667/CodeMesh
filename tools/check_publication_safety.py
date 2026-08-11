#!/usr/bin/env python3
"""Fail on high-confidence publication hazards in Git-visible files."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAX_TRACKED_FILE_BYTES = 1_000_000

TEXT_RULES = (
    (
        "private key material",
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    ("AWS access key", re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    (
        "GitHub token",
        re.compile(
            rb"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"
        ),
    ),
    ("Slack token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(rb"\bAIza[0-9A-Za-z_-]{30,}\b")),
    (
        "credential-bearing database URI",
        re.compile(
            rb"\b(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql)://"
            rb"[^\s$\"']+:[^\s@\"']+@"
        ),
    ),
    (
        "machine-specific absolute path",
        re.compile(
            rb"(?:\b[A-Za-z]:[\\/](?:Users|source|repos)[\\/]"
            rb"|/(?:home|Users)/[A-Za-z0-9._-]+/)"
        ),
    ),
)

CREDENTIAL_FILE_RULE = re.compile(
    r"(?:^|/)(?:id_rsa|id_ed25519|credentials|secrets?)(?:/|$)"
    r"|\.(?:pem|key|p12|pfx|jks|keystore)$",
    re.IGNORECASE,
)


def git_visible_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings: list[tuple[str, str]] = []

    for path in git_visible_files():
        relative = path.relative_to(ROOT).as_posix()
        if not path.is_file():
            continue

        if relative != ".env.example" and CREDENTIAL_FILE_RULE.search(relative):
            findings.append((relative, "credential-like filename"))

        size = path.stat().st_size
        if size > MAX_TRACKED_FILE_BYTES:
            findings.append((relative, f"file exceeds {MAX_TRACKED_FILE_BYTES} bytes"))

        data = path.read_bytes()
        if b"\0" in data:
            continue

        for label, pattern in TEXT_RULES:
            if pattern.search(data):
                findings.append((relative, label))

    if findings:
        print("Publication-safety check failed:")
        for relative, label in sorted(set(findings)):
            print(f"- {relative}: {label}")
        print("Sensitive values are intentionally not printed.")
        return 1

    print(
        f"Publication-safety check passed for {len(git_visible_files())} Git-visible files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
