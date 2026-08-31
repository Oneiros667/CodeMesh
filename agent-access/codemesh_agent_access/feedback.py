from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PACKET_SCHEMA_VERSION = "codemesh-feedback/v1"
SUMMARY_SCHEMA_VERSION = "codemesh-feedback-summary/v1"
OUTBOX_NAME = ".codemesh-feedback"

Classification = Literal["diagnostic", "controlled-evaluation"]
Confidence = Literal["low", "medium", "high"]
ValidationOutcome = Literal["passed", "failed", "not-run", "inconclusive"]
IssueCategory = Literal[
    "setup",
    "binding",
    "freshness",
    "missing-language",
    "missing-relationship",
    "ranking",
    "budget",
    "validation",
    "other",
]

_SENSITIVE_TEXT = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|password\s*=|passwd\s*=|token\s*=|"
    r"api[_-]?key\s*=|secret\s*=|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepositoryEvidence(_StrictModel):
    root: str
    branch: str
    commit: str
    dirty: bool


class CodeMeshEvidence(_StrictModel):
    commit: str
    dirty: bool | None = None
    working_tree_state_hash: str | None = None
    project_id: str
    checkout_id: str
    snapshot_id: str
    languages: list[str] = Field(min_length=1, max_length=8)
    parser_profile: str

    @field_validator("languages")
    @classmethod
    def canonical_languages(cls, value: list[str]) -> list[str]:
        canonical = sorted({item.strip().lower() for item in value if item.strip()})
        if not canonical:
            raise ValueError("at least one non-empty language is required")
        return canonical


class TaskEvidence(_StrictModel):
    family: str
    tools_attempted: list[str] = Field(default_factory=list, max_length=32)
    tools_called: list[str] = Field(default_factory=list, max_length=32)


class ResultEvidence(_StrictModel):
    helpful_paths: list[str] = Field(default_factory=list, max_length=32)
    incorrect_paths: list[str] = Field(default_factory=list, max_length=32)
    missed_paths: list[str] = Field(default_factory=list, max_length=32)
    stale_paths: list[str] = Field(default_factory=list, max_length=32)
    ambiguous_paths: list[str] = Field(default_factory=list, max_length=32)
    fallback_reason: str | None = None
    validation_outcome: ValidationOutcome


class IssueEvidence(_StrictModel):
    category: IssueCategory
    minimal_reproduction: str | None = None
    expected_targets: list[str] = Field(default_factory=list, max_length=32)
    proposed_correction: str | None = None
    supersedes_feedback_ids: list[str] = Field(default_factory=list, max_length=32)


class ReporterEvidence(_StrictModel):
    role: str
    confidence: Confidence


class FeedbackPacket(_StrictModel):
    schema_version: Literal["codemesh-feedback/v1"] = PACKET_SCHEMA_VERSION
    feedback_id: str
    recorded_at: datetime
    classification: Classification
    reporter: ReporterEvidence
    repository: RepositoryEvidence
    codemesh: CodeMeshEvidence
    task: TaskEvidence
    result: ResultEvidence
    issue: IssueEvidence


def record_feedback(
    *,
    repository_root: str | Path,
    role: str,
    classification: Classification,
    confidence: Confidence,
    project_id: str,
    checkout_id: str,
    snapshot_id: str,
    languages: list[str],
    parser_profile: str,
    task_family: str,
    issue_category: IssueCategory,
    validation_outcome: ValidationOutcome,
    tools_attempted: list[str] | None = None,
    tools_called: list[str] | None = None,
    helpful_paths: list[str] | None = None,
    incorrect_paths: list[str] | None = None,
    missed_paths: list[str] | None = None,
    stale_paths: list[str] | None = None,
    ambiguous_paths: list[str] | None = None,
    fallback_reason: str | None = None,
    minimal_reproduction: str | None = None,
    expected_targets: list[str] | None = None,
    proposed_correction: str | None = None,
    supersedes_feedback_ids: list[str] | None = None,
    codemesh_root: str | Path | None = None,
) -> tuple[FeedbackPacket, Path]:
    root = _exact_git_root(repository_root)
    _require_ignored_outbox(root)
    codemesh = _exact_git_root(codemesh_root or Path(__file__).resolve().parents[2])
    codemesh_dirty, codemesh_state_hash = _working_tree_state(codemesh)

    packet_data = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "recorded_at": datetime.now(UTC),
        "classification": classification,
        "reporter": {
            "role": _safe_text(role, "role", 80),
            "confidence": confidence,
        },
        "repository": {
            "root": str(root),
            "branch": _git(root, "branch", "--show-current") or "DETACHED",
            "commit": _git(root, "rev-parse", "HEAD"),
            "dirty": bool(
                _git(root, "status", "--porcelain", "--untracked-files=normal")
            ),
        },
        "codemesh": {
            "commit": _git(codemesh, "rev-parse", "HEAD"),
            "dirty": codemesh_dirty,
            "working_tree_state_hash": codemesh_state_hash,
            "project_id": _safe_text(project_id, "project_id", 160),
            "checkout_id": _safe_text(checkout_id, "checkout_id", 160),
            "snapshot_id": _safe_text(snapshot_id, "snapshot_id", 160),
            "languages": languages,
            "parser_profile": _safe_text(parser_profile, "parser_profile", 160),
        },
        "task": {
            "family": _safe_text(task_family, "task_family", 120),
            "tools_attempted": _safe_names(tools_attempted or [], "tools_attempted"),
            "tools_called": _safe_names(tools_called or [], "tools_called"),
        },
        "result": {
            "helpful_paths": _safe_paths(helpful_paths or [], root, "helpful_paths"),
            "incorrect_paths": _safe_paths(
                incorrect_paths or [], root, "incorrect_paths"
            ),
            "missed_paths": _safe_paths(missed_paths or [], root, "missed_paths"),
            "stale_paths": _safe_paths(stale_paths or [], root, "stale_paths"),
            "ambiguous_paths": _safe_paths(
                ambiguous_paths or [], root, "ambiguous_paths"
            ),
            "fallback_reason": _safe_optional_text(
                fallback_reason, "fallback_reason", 400
            ),
            "validation_outcome": validation_outcome,
        },
        "issue": {
            "category": issue_category,
            "minimal_reproduction": _safe_optional_text(
                minimal_reproduction, "minimal_reproduction", 500
            ),
            "expected_targets": _safe_paths(
                expected_targets or [], root, "expected_targets"
            ),
            "proposed_correction": _safe_optional_text(
                proposed_correction, "proposed_correction", 500
            ),
            "supersedes_feedback_ids": _safe_feedback_ids(
                supersedes_feedback_ids or []
            ),
        },
    }
    normalized = FeedbackPacket.model_validate(
        {**packet_data, "feedback_id": "feedback-pending"}
    ).model_dump(mode="json", exclude={"feedback_id"})
    feedback_id = _content_id(normalized)
    packet = FeedbackPacket.model_validate({**normalized, "feedback_id": feedback_id})
    outbox = root / OUTBOX_NAME
    outbox.mkdir(exist_ok=True)
    output = outbox / f"{feedback_id}.json"
    output.write_text(
        json.dumps(packet.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return packet, output


def validate_feedback(path: str | Path) -> FeedbackPacket:
    source = Path(path).resolve(strict=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    packet = FeedbackPacket.model_validate(payload)
    expected_id = _content_id(
        {key: value for key, value in payload.items() if key != "feedback_id"}
    )
    if packet.feedback_id != expected_id:
        raise ValueError(
            f"Feedback id mismatch for {source}: expected {expected_id}, "
            f"found {packet.feedback_id}."
        )
    return packet


def summarize_feedback(roots: list[str | Path]) -> dict[str, object]:
    if not roots:
        raise ValueError("At least one managed checkout root is required.")

    packets: list[tuple[FeedbackPacket, Path]] = []
    seen: set[str] = set()
    for root_value in roots:
        root = _exact_git_root(root_value)
        outbox = root / OUTBOX_NAME
        if not outbox.is_dir():
            continue
        for path in sorted(outbox.glob("*.json")):
            packet = validate_feedback(path)
            if Path(packet.repository.root).resolve() != root:
                raise ValueError(
                    f"Feedback packet {path} claims repository root "
                    f"{packet.repository.root}, expected {root}."
                )
            if packet.feedback_id not in seen:
                seen.add(packet.feedback_id)
                packets.append((packet, path))

    groups: dict[tuple[str, str, tuple[str, ...]], list[FeedbackPacket]] = defaultdict(
        list
    )
    for packet, _ in packets:
        key = (
            packet.issue.category,
            packet.task.family,
            tuple(packet.codemesh.languages),
        )
        groups[key].append(packet)

    ranked = []
    for (category, task_family, languages), members in groups.items():
        superseded = {
            feedback_id
            for member in members
            if member.result.validation_outcome == "passed"
            for feedback_id in member.issue.supersedes_feedback_ids
        }
        unresolved_failures = [
            member.feedback_id
            for member in members
            if member.result.validation_outcome == "failed"
            and member.feedback_id not in superseded
        ]
        all_passed = all(
            member.result.validation_outcome == "passed" for member in members
        )
        resolved = bool(superseded) and not unresolved_failures
        verified = all_passed and not superseded
        status = "resolved" if resolved else "verified" if verified else "open"
        score = (
            0
            if status in {"resolved", "verified"}
            else _priority_score(category, members)
        )
        ranked.append(
            {
                "status": status,
                "priority": _priority_label(score),
                "priority_score": score,
                "issue_category": category,
                "task_family": task_family,
                "languages": list(languages),
                "occurrences": len(members),
                "validation_outcomes": _counts(
                    member.result.validation_outcome for member in members
                ),
                "roles": sorted({member.reporter.role for member in members}),
                "proposed_corrections": sorted(
                    {
                        member.issue.proposed_correction
                        for member in members
                        if member.issue.proposed_correction
                    }
                ),
                "superseded_feedback_ids": sorted(superseded),
                "unresolved_failure_ids": sorted(unresolved_failures),
                "provenance": [
                    {
                        "feedback_id": member.feedback_id,
                        "recorded_at": member.recorded_at.isoformat(),
                        "repository_commit": member.repository.commit,
                        "codemesh_commit": member.codemesh.commit,
                        "codemesh_dirty": member.codemesh.dirty,
                        "codemesh_working_tree_state_hash": (
                            member.codemesh.working_tree_state_hash
                        ),
                        "project_id": member.codemesh.project_id,
                        "checkout_id": member.codemesh.checkout_id,
                        "snapshot_id": member.codemesh.snapshot_id,
                    }
                    for member in sorted(members, key=lambda item: item.feedback_id)
                ],
            }
        )
    ranked.sort(
        key=lambda item: (
            -int(item["priority_score"]),
            str(item["issue_category"]),
            str(item["task_family"]),
        )
    )
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "packet_count": len(packets),
        "invalid_packet_count": 0,
        "source_outboxes": sorted({str(path.parent.resolve()) for _, path in packets}),
        "priorities": ranked,
    }


def _exact_git_root(value: str | Path) -> Path:
    candidate = Path(value).expanduser().resolve(strict=True)
    if not candidate.is_dir():
        raise ValueError(f"Repository root is not a directory: {candidate}")
    discovered = Path(_git(candidate, "rev-parse", "--show-toplevel")).resolve()
    if discovered != candidate:
        raise ValueError(
            f"Repository root must be exact: supplied {candidate}, git reports {discovered}."
        )
    return discovered


def _require_ignored_outbox(root: Path) -> None:
    probe = f"{OUTBOX_NAME}/_codemesh-ignore-probe.json"
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", probe],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(
            f"{root / OUTBOX_NAME} is not ignored. Add '/{OUTBOX_NAME}/' to "
            ".gitignore through the checkout's managed instance configuration first."
        )


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise ValueError(f"git {' '.join(arguments)} failed in {root}: {detail}")
    return result.stdout.strip()


def _safe_names(values: list[str], field: str) -> list[str]:
    return sorted({_safe_text(value, field, 120) for value in values})


def _safe_feedback_ids(values: list[str]) -> list[str]:
    identifiers = _safe_names(values, "supersedes_feedback_ids")
    invalid = [
        value
        for value in identifiers
        if not re.fullmatch(r"feedback-[0-9a-f]{20}", value)
    ]
    if invalid:
        raise ValueError(
            "supersedes_feedback_ids contains invalid feedback id(s): "
            + ", ".join(invalid)
        )
    return identifiers


def _safe_paths(values: list[str], root: Path, field: str) -> list[str]:
    paths: set[str] = set()
    for value in values:
        text = _safe_text(value, field, 300).replace("\\", "/")
        candidate = Path(text)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"{field} must contain repository-relative paths: {value}")
        resolved = (root / candidate).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError(f"{field} escapes repository root: {value}")
        paths.add(candidate.as_posix())
    return sorted(paths)


def _safe_optional_text(value: str | None, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _safe_text(value, field, maximum)


def _safe_text(value: str, field: str, maximum: int) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field} must not be empty.")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters.")
    if any(ord(character) < 32 for character in text):
        raise ValueError(f"{field} contains control characters.")
    if _SENSITIVE_TEXT.search(text):
        raise ValueError(f"{field} appears to contain a credential or secret.")
    return text


def _content_id(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"feedback-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:20]}"


def _working_tree_state(root: Path) -> tuple[bool, str | None]:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    if not status:
        return False, None

    digest = hashlib.sha256()
    digest.update(status)
    digest.update(
        subprocess.run(
            ["git", "diff", "--binary", "HEAD", "--"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    for raw_path in sorted(path for path in untracked if path):
        path = root / raw_path.decode("utf-8", errors="surrogateescape")
        digest.update(raw_path)
        if path.is_file():
            digest.update(path.read_bytes())
    return True, digest.hexdigest()


def _counts(values: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:  # type: ignore[union-attr]
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _priority_score(category: str, members: list[FeedbackPacket]) -> int:
    category_weight = {
        "binding": 5,
        "freshness": 5,
        "setup": 4,
        "missing-language": 4,
        "missing-relationship": 4,
        "ranking": 3,
        "validation": 3,
        "budget": 2,
        "other": 1,
    }[category]
    failure_weight = sum(
        2 if member.result.validation_outcome == "failed" else 1
        for member in members
        if member.result.validation_outcome in {"failed", "inconclusive"}
    )
    incorrect_weight = sum(
        bool(member.result.incorrect_paths or member.result.stale_paths)
        for member in members
    )
    return category_weight + min(len(members), 5) + failure_weight + incorrect_weight


def _priority_label(score: int) -> str:
    if score >= 8:
        return "high"
    if score >= 5:
        return "medium"
    return "low"
