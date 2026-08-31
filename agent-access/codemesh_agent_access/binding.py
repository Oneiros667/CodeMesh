from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any


class RepositoryBindingError(RuntimeError):
    """Raised when a repository-scoped operation cannot honor its binding."""


@dataclass(frozen=True)
class RepositoryBinding:
    project_id: str
    checkout_id: str
    repository_root: str
    source_view_hash: str | None = None

    def __post_init__(self) -> None:
        project_id = self.project_id.strip()
        checkout_id = self.checkout_id.strip()
        repository_root = self.repository_root.strip()
        source_view_hash = (self.source_view_hash or "").strip() or None
        if not project_id:
            raise ValueError("CodeMesh repository binding requires a project id.")
        if not checkout_id:
            raise ValueError("CodeMesh repository binding requires a checkout id.")
        if not repository_root:
            raise ValueError("CodeMesh repository binding requires a repository root.")

        root = Path(repository_root).expanduser()
        if not root.is_absolute():
            raise ValueError(
                "CodeMesh repository binding root must be an absolute path."
            )

        object.__setattr__(self, "project_id", project_id)
        object.__setattr__(self, "checkout_id", checkout_id)
        object.__setattr__(self, "repository_root", str(root.resolve(strict=False)))
        object.__setattr__(self, "source_view_hash", source_view_hash)

    def accepts(self, repository_id: str | None) -> bool:
        if repository_id is None or not repository_id.strip():
            return True
        return repository_id.strip() in {self.project_id, self.checkout_id}

    def as_dict(self) -> dict[str, str | None]:
        return {
            "project_id": self.project_id,
            "checkout_id": self.checkout_id,
            "repository_root": self.repository_root,
            "source_view_hash": self.source_view_hash,
        }


def binding_from_values(
    project_id: str | None = None,
    checkout_id: str | None = None,
    repository_root: str | None = None,
    source_view_hash: str | None = None,
) -> RepositoryBinding | None:
    values = {
        "project_id": project_id or os.getenv("CODEMESH_PROJECT_ID"),
        "checkout_id": checkout_id or os.getenv("CODEMESH_CHECKOUT_ID"),
        "repository_root": repository_root or os.getenv("CODEMESH_REPOSITORY_ROOT"),
        "source_view_hash": source_view_hash or os.getenv("CODEMESH_SOURCE_VIEW_HASH"),
    }
    required = ["project_id", "checkout_id", "repository_root"]
    present = [name for name in required if (values[name] or "").strip()]
    if not present:
        if (values["source_view_hash"] or "").strip():
            raise ValueError(
                "CODEMESH_SOURCE_VIEW_HASH cannot be used without a complete "
                "project, checkout, and repository-root binding."
            )
        return None
    if len(present) != len(required):
        missing = ", ".join(
            name.replace("_", "-") for name in required if name not in present
        )
        raise ValueError(f"Incomplete CodeMesh repository binding; missing: {missing}.")

    return RepositoryBinding(
        project_id=str(values["project_id"]),
        checkout_id=str(values["checkout_id"]),
        repository_root=str(values["repository_root"]),
        source_view_hash=(
            str(values["source_view_hash"]) if values["source_view_hash"] else None
        ),
    )


def bound_repository_reference(
    binding: RepositoryBinding | None,
    repository_id: str | None,
    *,
    required_when_unbound: bool,
) -> str | None:
    if binding is not None:
        if not binding.accepts(repository_id):
            raise RepositoryBindingError(
                f"Repository reference '{repository_id}' does not match the configured "
                f"project '{binding.project_id}' and checkout '{binding.checkout_id}'."
            )
        return binding.project_id

    if required_when_unbound and not (repository_id or "").strip():
        raise RepositoryBindingError(
            "Repository selection is required because this CodeMesh server is unbound."
        )
    return repository_id


def assess_binding(
    binding: RepositoryBinding,
    repository: Any | None,
    freshness: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    if repository is None:
        issues.append("bound_repository_missing")
    else:
        if repository.project_id != binding.project_id:
            issues.append("project_mismatch")
        if repository.checkout_id != binding.checkout_id:
            issues.append("checkout_mismatch")
        if not _same_path(repository.root_path, binding.repository_root):
            issues.append("repository_root_mismatch")
        if (
            binding.source_view_hash
            and repository.source_view_hash != binding.source_view_hash
        ):
            issues.append("source_view_hash_mismatch")

    if freshness.get("status") != "fresh" or freshness.get("is_stale") is not False:
        issues.append("snapshot_not_fresh")
    if freshness.get("provenance_status") != "known":
        issues.append("snapshot_provenance_unknown")

    return {
        "status": "accepted" if not issues else "rejected",
        "issues": list(dict.fromkeys(issues)),
        "project_id": binding.project_id,
        "checkout_id": binding.checkout_id,
        "repository_root": binding.repository_root,
        "source_view_hash": binding.source_view_hash,
    }


def require_accepted_binding(assessment: dict[str, Any]) -> None:
    if assessment.get("status") == "accepted":
        return
    issues = ", ".join(str(value) for value in assessment.get("issues", []))
    raise RepositoryBindingError(
        "CodeMesh refused repository context because the configured binding was "
        f"not accepted: {issues or 'unknown_binding_failure'}."
    )


def _same_path(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return os.path.normcase(os.path.realpath(left)) == os.path.normcase(
        os.path.realpath(right)
    )
