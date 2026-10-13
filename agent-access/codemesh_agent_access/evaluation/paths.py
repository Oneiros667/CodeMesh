from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath


ARTIFACT_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}


def validate_artifact_id(value: str) -> str:
    if (
        re.fullmatch(ARTIFACT_ID_PATTERN, value) is None
        or value.endswith(".")
        or value.split(".", 1)[0].upper() in _RESERVED_NAMES
    ):
        raise ValueError(
            "Evaluation identifiers must be safe path segments: ASCII letters, "
            "digits, underscores, hyphens, and internal dots; no path syntax, "
            "trailing dot, or reserved device name."
        )
    return value


def validate_setup_patch_name(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or path.is_absolute()
        or PureWindowsPath(value).drive
        or ".." in path.parts
    ):
        raise ValueError("Setup patches must use contained suite-relative paths.")
    return value


def resolve_setup_patch(suite_path: Path, relative: str) -> Path:
    validate_setup_patch_name(relative)
    try:
        root = suite_path.parent.resolve(strict=True)
        path = (root / relative).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(
            "Setup patch must be an accessible suite-relative file."
        ) from exc
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Setup patch must be a file within its suite directory.")
    return path


def managed_artifact_path(root: Path, *parts: str) -> Path:
    """Keep generated destinations inside the operator-selected artifact root."""
    resolved_root = root.resolve()
    path = resolved_root.joinpath(*parts).resolve()
    if path == resolved_root or not path.is_relative_to(resolved_root):
        raise ValueError("Generated artifact path escapes its managed directory.")
    return path
