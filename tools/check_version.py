#!/usr/bin/env python3
"""Verify synchronized source version declarations without importing the app."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path


def validate(root: Path) -> str:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if (
        re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version)
        is None
    ):
        raise ValueError("VERSION must contain a three-part numeric version.")
    package = root / "agent-access"
    project = tomllib.loads((package / "pyproject.toml").read_text(encoding="utf-8"))
    module = ast.parse(
        (package / "codemesh_agent_access/__init__.py").read_text(encoding="utf-8")
    )
    exported = next(
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        )
    )
    lock = tomllib.loads((package / "uv.lock").read_text(encoding="utf-8"))
    locked = next(
        item["version"]
        for item in lock["package"]
        if item["name"] == project["project"]["name"]
    )
    for name, actual in {
        "pyproject.toml": project["project"]["version"],
        "__version__": exported,
        "uv.lock": locked,
    }.items():
        if actual != version:
            raise ValueError(
                f"{name} version {actual!r} differs from VERSION {version!r}."
            )
    return version


if __name__ == "__main__":
    print(
        f"Version declarations agree: {validate(Path(__file__).resolve().parents[1])}"
    )
