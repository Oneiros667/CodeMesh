from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PACKET_SCHEMA_VERSION = "codemesh-feedback/v1"
PACKET_SCHEMA_VERSION_V2 = "codemesh-feedback/v2"
SUMMARY_SCHEMA_VERSION = "codemesh-feedback-summary/v1"
RESOLUTION_PLAN_SCHEMA_VERSION = "codemesh-feedback-resolution-plan/v1"
OUTBOX_NAME = ".codemesh-feedback"

if TYPE_CHECKING:
    from .feedback_session import SessionRuntime

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
    r"(?i)(authorization\s*:|bearer\s+|password\s*[:=]|passwd\s*[:=]|"
    r"token\s*[:=]|api[_-]?key\s*[:=]|secret\s*[:=]|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
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


class SessionEvidence(_StrictModel):
    session_id: str
    profile: Literal["development-feedback"] = "development-feedback"
    local_only: Literal[True] = True

    @field_validator("session_id")
    @classmethod
    def session_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"session-[0-9a-f]{20}", value):
            raise ValueError("Feedback session id has an invalid shape.")
        return value


class BindingEvidence(_StrictModel):
    status: Literal["accepted", "unavailable"]
    diagnostic_code: str | None = None

    @model_validator(mode="after")
    def diagnostic_matches_status(self) -> BindingEvidence:
        if self.status == "unavailable" and not self.diagnostic_code:
            raise ValueError(
                "Unavailable feedback provenance requires a diagnostic code."
            )
        if self.status == "accepted" and self.diagnostic_code is not None:
            raise ValueError("Accepted feedback provenance cannot have a failure code.")
        return self


class CodeMeshEvidenceV2(_StrictModel):
    commit: str
    dirty: bool
    working_tree_state_hash: str | None = None
    project_id: str
    checkout_id: str
    snapshot_id: str | None = None
    languages: list[str] = Field(default_factory=list, max_length=8)
    parser_profile: str | None = None
    binding: BindingEvidence

    @field_validator("languages")
    @classmethod
    def canonical_languages(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().lower() for item in value if item.strip()})


class ToolTraceEvent(_StrictModel):
    sequence: int = Field(ge=1)
    tool: str
    outcome: Literal["succeeded", "failed"]
    diagnostic_code: str | None = None


class TaskEvidenceV2(_StrictModel):
    family: str
    recent_tool_events: list[ToolTraceEvent] = Field(
        default_factory=list, max_length=32
    )
    association: Literal["same_server_recent_window"] = "same_server_recent_window"


class ResultEvidenceV2(_StrictModel):
    helpful_paths: list[str] = Field(default_factory=list, max_length=64)
    incorrect_paths: list[str] = Field(default_factory=list, max_length=64)
    missed_paths: list[str] = Field(default_factory=list, max_length=64)
    stale_paths: list[str] = Field(default_factory=list, max_length=64)
    ambiguous_paths: list[str] = Field(default_factory=list, max_length=64)
    fallback_reason: str | None = None
    validation_outcome: ValidationOutcome


class IssueEvidenceV2(_StrictModel):
    category: IssueCategory
    minimal_reproduction: str | None = None
    expected_targets: list[str] = Field(default_factory=list, max_length=64)
    proposed_correction: str | None = None
    supersedes_feedback_ids: list[str] = Field(default_factory=list, max_length=32)


class FeedbackPacketV2(_StrictModel):
    schema_version: Literal["codemesh-feedback/v2"] = PACKET_SCHEMA_VERSION_V2
    feedback_id: str
    recorded_at: datetime
    classification: Literal["diagnostic"] = "diagnostic"
    session: SessionEvidence
    reporter: ReporterEvidence
    repository: RepositoryEvidence
    codemesh: CodeMeshEvidenceV2
    task: TaskEvidenceV2
    result: ResultEvidenceV2
    issue: IssueEvidenceV2

    @model_validator(mode="after")
    def category_provenance(self) -> FeedbackPacketV2:
        if self.issue.category not in {"setup", "binding", "freshness"} and (
            self.codemesh.binding.status != "accepted"
            or not self.codemesh.snapshot_id
            or not self.codemesh.languages
            or not self.codemesh.parser_profile
        ):
            raise ValueError(
                f"{self.issue.category} feedback requires accepted snapshot and parser provenance."
            )
        if (
            self.issue.supersedes_feedback_ids
            and self.result.validation_outcome != "passed"
        ):
            raise ValueError("Only a passing recheck may supersede earlier feedback.")
        return self


FeedbackPacketType = FeedbackPacket | FeedbackPacketV2


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
    outbox = root / OUTBOX_NAME
    if outbox.is_symlink() or outbox.is_junction() or outbox.resolve() != outbox:
        raise ValueError("Feedback outbox must be a local directory in the checkout.")
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
    _validate_packet_safety(packet)
    outbox.mkdir(exist_ok=True)
    output = outbox / f"{feedback_id}.json"
    with output.open("x", encoding="utf-8") as stream:
        stream.write(
            json.dumps(packet.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        )
    return packet, output


def record_development_feedback(
    *,
    runtime: SessionRuntime,
    confidence: Confidence,
    task_family: str,
    issue_category: IssueCategory,
    validation_outcome: ValidationOutcome,
    provenance: dict[str, Any],
    recent_tool_events: list[dict[str, Any]] | None = None,
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
) -> tuple[FeedbackPacketV2, Path]:
    session = runtime.assert_active()
    root = _exact_git_root(runtime.binding.repository_root)
    participant = runtime.participant
    if (
        participant.project_id != runtime.binding.project_id
        or participant.checkout_id != runtime.binding.checkout_id
        or Path(participant.repository_root).resolve() != root
    ):
        raise ValueError(
            "Development feedback runtime binding changed after activation."
        )
    outbox = root / OUTBOX_NAME
    _validate_outbox(root, outbox)
    existing_packets = (
        len(list(outbox.glob("feedback-*.json"))) if outbox.exists() else 0
    )
    if existing_packets >= session.bounds.max_packets:
        raise ValueError("Development feedback session packet limit has been reached.")

    availability = str(provenance.get("status") or "unavailable")
    if availability not in {"accepted", "unavailable"}:
        raise ValueError("Feedback provenance status must be accepted or unavailable.")
    snapshot_id = _safe_optional_text(
        _optional_string(provenance.get("snapshot_id")),
        "snapshot_id",
        160,
    )
    parser_profile = _safe_optional_text(
        _optional_string(provenance.get("parser_profile")),
        "parser_profile",
        160,
    )
    languages = [str(value) for value in provenance.get("languages") or []]
    diagnostic_code = _safe_optional_name(
        _optional_string(provenance.get("diagnostic_code")),
        "diagnostic_code",
    )
    provenance_required = issue_category not in {"setup", "binding", "freshness"}
    if provenance_required and (
        availability != "accepted"
        or not snapshot_id
        or not languages
        or not parser_profile
    ):
        raise ValueError(
            f"{issue_category} feedback requires accepted snapshot and parser provenance."
        )

    codemesh_root = _exact_git_root(session.codemesh.repository_root)
    codemesh_dirty, codemesh_state_hash = _working_tree_state(codemesh_root)
    text_limit = session.bounds.max_text_characters
    path_limit = session.bounds.max_paths
    path_fields = {
        "helpful_paths": helpful_paths or [],
        "incorrect_paths": incorrect_paths or [],
        "missed_paths": missed_paths or [],
        "stale_paths": stale_paths or [],
        "ambiguous_paths": ambiguous_paths or [],
        "expected_targets": expected_targets or [],
    }
    for field, values in path_fields.items():
        if len(values) > path_limit:
            raise ValueError(f"{field} exceeds the session path limit of {path_limit}.")

    packet_data = {
        "schema_version": PACKET_SCHEMA_VERSION_V2,
        "recorded_at": runtime.clock(),
        "classification": "diagnostic",
        "session": {
            "session_id": session.session_id,
            "profile": "development-feedback",
            "local_only": True,
        },
        "reporter": {
            "role": participant.reporter_role,
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
            "commit": _git(codemesh_root, "rev-parse", "HEAD"),
            "dirty": codemesh_dirty,
            "working_tree_state_hash": codemesh_state_hash,
            "project_id": participant.project_id,
            "checkout_id": participant.checkout_id,
            "snapshot_id": snapshot_id,
            "languages": languages,
            "parser_profile": parser_profile,
            "binding": {
                "status": availability,
                "diagnostic_code": diagnostic_code,
            },
        },
        "task": {
            "family": _safe_text(task_family, "task_family", 120),
            "recent_tool_events": recent_tool_events or [],
            "association": "same_server_recent_window",
        },
        "result": {
            "helpful_paths": _safe_paths(
                path_fields["helpful_paths"], root, "helpful_paths"
            ),
            "incorrect_paths": _safe_paths(
                path_fields["incorrect_paths"], root, "incorrect_paths"
            ),
            "missed_paths": _safe_paths(
                path_fields["missed_paths"], root, "missed_paths"
            ),
            "stale_paths": _safe_paths(path_fields["stale_paths"], root, "stale_paths"),
            "ambiguous_paths": _safe_paths(
                path_fields["ambiguous_paths"], root, "ambiguous_paths"
            ),
            "fallback_reason": _safe_optional_text(
                fallback_reason, "fallback_reason", text_limit
            ),
            "validation_outcome": validation_outcome,
        },
        "issue": {
            "category": issue_category,
            "minimal_reproduction": _safe_optional_text(
                minimal_reproduction, "minimal_reproduction", text_limit
            ),
            "expected_targets": _safe_paths(
                path_fields["expected_targets"], root, "expected_targets"
            ),
            "proposed_correction": _safe_optional_text(
                proposed_correction, "proposed_correction", text_limit
            ),
            "supersedes_feedback_ids": _safe_feedback_ids(
                supersedes_feedback_ids or []
            ),
        },
    }
    normalized = FeedbackPacketV2.model_validate(
        {**packet_data, "feedback_id": "feedback-pending"}
    ).model_dump(mode="json", exclude={"feedback_id"})
    feedback_id = _content_id(normalized)
    packet = FeedbackPacketV2.model_validate({**normalized, "feedback_id": feedback_id})
    _validate_packet_safety(packet)
    outbox.mkdir(exist_ok=True)
    output = outbox / f"{feedback_id}.json"
    with output.open("x", encoding="utf-8") as stream:
        stream.write(
            json.dumps(packet.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        )
    return packet, output


def validate_feedback(path: str | Path) -> FeedbackPacketType:
    requested = Path(path)
    if (
        requested.is_symlink()
        or requested.is_junction()
        or not requested.is_file()
        or requested.stat().st_nlink != 1
    ):
        raise ValueError("Feedback packet must be an unlinked regular file.")
    source = requested.resolve(strict=True)
    if source.stat().st_size > 65_536:
        raise ValueError("Feedback packet exceeds the 65,536-byte validation limit.")
    payload = json.loads(source.read_text(encoding="utf-8"))
    schema_version = payload.get("schema_version")
    if schema_version == PACKET_SCHEMA_VERSION:
        packet: FeedbackPacketType = FeedbackPacket.model_validate(payload)
    elif schema_version == PACKET_SCHEMA_VERSION_V2:
        packet = FeedbackPacketV2.model_validate(payload)
    else:
        raise ValueError(f"Unsupported CodeMesh feedback schema: {schema_version}.")
    expected_id = _content_id(
        {key: value for key, value in payload.items() if key != "feedback_id"}
    )
    if packet.feedback_id != expected_id:
        raise ValueError(
            f"Feedback id mismatch for {source}: expected {expected_id}, "
            f"found {packet.feedback_id}."
        )
    _validate_packet_safety(packet)
    return packet


def summarize_feedback(roots: list[str | Path]) -> dict[str, object]:
    if not roots:
        raise ValueError("At least one managed checkout root is required.")

    packets: list[tuple[FeedbackPacketType, Path]] = []
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

    groups: dict[tuple[str, str, tuple[str, ...]], list[FeedbackPacketType]] = (
        defaultdict(list)
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
        superseded = _superseded_feedback_ids(members)
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


def list_session_feedback(
    runtime: SessionRuntime,
    *,
    include_legacy: bool = False,
    state: Literal["open", "resolved", "verified"] | None = None,
    category: IssueCategory | None = None,
    task_family: str | None = None,
    language: str | None = None,
    reporter_role: str | None = None,
    feedback_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, object]:
    session = _require_maintainer_runtime(runtime)
    if offset < 0 or limit < 1 or limit > 100:
        raise ValueError("Feedback pagination requires offset >= 0 and limit 1..100.")
    packets, invalid = _session_packets(runtime, include_legacy=include_legacy)
    superseded = _superseded_feedback_ids([packet for packet, _path, _scope in packets])
    rows: list[dict[str, object]] = []
    for packet, path, scope in packets:
        packet_state = _packet_state(packet, superseded)
        languages = list(packet.codemesh.languages)
        if state and packet_state != state:
            continue
        if category and packet.issue.category != category:
            continue
        if task_family and packet.task.family != task_family:
            continue
        if language and language.casefold() not in {
            item.casefold() for item in languages
        }:
            continue
        if reporter_role and packet.reporter.role != reporter_role:
            continue
        if feedback_id and packet.feedback_id != feedback_id:
            continue
        rows.append(
            {
                "feedback_id": packet.feedback_id,
                "schema_version": packet.schema_version,
                "session_scope": scope,
                "state": packet_state,
                "recorded_at": packet.recorded_at.isoformat(),
                "category": packet.issue.category,
                "task_family": packet.task.family,
                "validation_outcome": packet.result.validation_outcome,
                "confidence": packet.reporter.confidence,
                "reporter_role": packet.reporter.role,
                "languages": languages,
                "checkout_id": packet.codemesh.checkout_id,
                "packet_path": (
                    f"{packet.codemesh.checkout_id}/{OUTBOX_NAME}/{path.name}"
                ),
            }
        )
    rows.sort(key=lambda item: (str(item["recorded_at"]), str(item["feedback_id"])))
    selected = rows[offset : offset + limit]
    return {
        "schema_version": "codemesh-session-feedback-list/v1",
        "session_id": session.session_id,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": selected,
        "invalid_packets": invalid[:100],
        "invalid_packet_count": len(invalid),
        "human_review_required": True,
    }


def get_session_feedback(
    runtime: SessionRuntime,
    feedback_id: str,
    *,
    include_legacy: bool = False,
) -> dict[str, object]:
    session = _require_maintainer_runtime(runtime)
    identifier = _safe_feedback_ids([feedback_id])[0]
    packets, invalid = _session_packets(runtime, include_legacy=include_legacy)
    matches = [item for item in packets if item[0].feedback_id == identifier]
    if len(matches) != 1:
        if not matches:
            raise ValueError(
                f"Feedback id was not found in this session: {identifier}."
            )
        raise ValueError(
            f"Feedback id is ambiguous across session outboxes: {identifier}."
        )
    packet, _path, scope = matches[0]
    superseded = _superseded_feedback_ids(
        [candidate for candidate, _candidate_path, _candidate_scope in packets]
    )
    return {
        "schema_version": "codemesh-session-feedback-detail/v1",
        "session_id": session.session_id,
        "session_scope": scope,
        "state": _packet_state(packet, superseded),
        "packet": packet.model_dump(mode="json"),
        "invalid_packet_count": len(invalid),
        "human_review_required": True,
    }


def prepare_feedback_resolution(
    runtime: SessionRuntime,
    *,
    feedback_ids: list[str],
    reproduction_state: Literal["reproduced", "not-reproduced", "blocked"],
    change_summary: str,
    proposed_paths: list[str],
    risks: list[str] | None = None,
    required_tests: list[str] | None = None,
    unresolved_questions: list[str] | None = None,
    include_legacy: bool = False,
) -> dict[str, object]:
    session = _require_maintainer_runtime(runtime)
    identifiers = _safe_feedback_ids(feedback_ids)
    if not identifiers:
        raise ValueError("At least one feedback id is required.")
    details = [
        get_session_feedback(runtime, identifier, include_legacy=include_legacy)
        for identifier in identifiers
    ]
    codemesh_root = _exact_git_root(session.codemesh.repository_root)
    paths = _safe_paths(proposed_paths, codemesh_root, "proposed_paths")
    if not paths:
        raise ValueError("At least one proposed CodeMesh-relative path is required.")
    packet_provenance = []
    for detail in details:
        packet = detail["packet"]
        assert isinstance(packet, dict)
        repository = packet["repository"]
        codemesh = packet["codemesh"]
        assert isinstance(repository, dict) and isinstance(codemesh, dict)
        packet_provenance.append(
            {
                "feedback_id": packet["feedback_id"],
                "session_scope": detail["session_scope"],
                "repository_commit": repository["commit"],
                "codemesh_commit": codemesh["commit"],
                "snapshot_id": codemesh.get("snapshot_id"),
            }
        )
    unsigned = {
        "schema_version": RESOLUTION_PLAN_SCHEMA_VERSION,
        "session_id": session.session_id,
        "feedback_ids": identifiers,
        "feedback_provenance": sorted(
            packet_provenance,
            key=lambda item: str(item["feedback_id"]),
        ),
        "reproduction_state": reproduction_state,
        "change_summary": _safe_text(change_summary, "change_summary", 1000),
        "proposed_paths": paths,
        "risks": _safe_text_list(risks or [], "risks", 500, 32),
        "required_tests": _safe_text_list(
            required_tests or [], "required_tests", 300, 32
        ),
        "unresolved_questions": _safe_text_list(
            unresolved_questions or [], "unresolved_questions", 500, 32
        ),
        "evidence_boundary": (
            "This deterministic plan is diagnostic product input. It is not human "
            "approval, implementation evidence, release authority, or product-benefit evidence."
        ),
        "human_review_required": True,
        "human_approved": False,
    }
    return {**unsigned, "plan_hash": _hash_payload(unsigned)}


def _session_packets(
    runtime: SessionRuntime,
    *,
    include_legacy: bool,
) -> tuple[list[tuple[FeedbackPacketType, Path, str]], list[dict[str, str]]]:
    session = _require_maintainer_runtime(runtime)
    packets: list[tuple[FeedbackPacketType, Path, str]] = []
    invalid: list[dict[str, str]] = []
    for participant in session.clients:
        root = _exact_git_root(participant.repository_root)
        outbox = root / OUTBOX_NAME
        if outbox.is_symlink() or outbox.is_junction() or outbox.resolve() != outbox:
            invalid.append(
                {"checkout_id": participant.checkout_id, "code": "unsafe_outbox"}
            )
            continue
        if not outbox.is_dir():
            continue
        for path in sorted(outbox.glob("*.json")):
            try:
                if (
                    not path.is_file()
                    or path.is_symlink()
                    or path.is_junction()
                    or path.resolve().parent != outbox.resolve()
                    or path.stat().st_nlink != 1
                ):
                    raise ValueError("unsafe_packet_file")
                packet = validate_feedback(path)
                if Path(packet.repository.root).resolve() != root:
                    raise ValueError("claimed_root_mismatch")
                if isinstance(packet, FeedbackPacketV2):
                    if packet.session.session_id != session.session_id:
                        continue
                    scope = "active_session"
                elif include_legacy:
                    scope = "legacy_unscoped"
                else:
                    continue
                packets.append((packet, path, scope))
            except (OSError, ValueError, json.JSONDecodeError):
                invalid.append(
                    {
                        "checkout_id": participant.checkout_id,
                        "packet": path.name,
                        "code": "invalid_packet",
                    }
                )
    return packets, invalid


def _require_maintainer_runtime(runtime: SessionRuntime) -> Any:
    if runtime.profile != "feedback-maintainer":
        raise ValueError("Feedback intake requires the feedback-maintainer profile.")
    return runtime.assert_active()


def _packet_state(packet: FeedbackPacketType, superseded: set[str]) -> str:
    if packet.feedback_id in superseded:
        return "resolved"
    if packet.result.validation_outcome == "passed":
        return "verified"
    return "open"


def _superseded_feedback_ids(packets: list[FeedbackPacketType]) -> set[str]:
    by_id = {packet.feedback_id: packet for packet in packets}
    superseded: set[str] = set()
    for recheck in packets:
        if recheck.result.validation_outcome != "passed":
            continue
        for identifier in recheck.issue.supersedes_feedback_ids:
            original = by_id.get(identifier)
            if (
                original is not None
                and original.result.validation_outcome != "passed"
                and original.repository.root == recheck.repository.root
                and original.issue.category == recheck.issue.category
                and original.task.family == recheck.task.family
            ):
                superseded.add(identifier)
    return superseded


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


def _validate_packet_safety(packet: FeedbackPacketType) -> None:
    root = Path(packet.repository.root).expanduser()
    if not root.is_absolute():
        raise ValueError("Feedback repository root must be absolute.")
    root = root.resolve(strict=False)
    text_fields: list[tuple[str | None, str, int]] = [
        (packet.reporter.role, "reporter.role", 80),
        (packet.repository.branch, "repository.branch", 200),
        (packet.repository.commit, "repository.commit", 160),
        (packet.codemesh.commit, "codemesh.commit", 160),
        (packet.codemesh.project_id, "codemesh.project_id", 160),
        (packet.codemesh.checkout_id, "codemesh.checkout_id", 160),
        (packet.codemesh.snapshot_id, "codemesh.snapshot_id", 160),
        (packet.codemesh.parser_profile, "codemesh.parser_profile", 160),
        (packet.task.family, "task.family", 120),
        (packet.result.fallback_reason, "result.fallback_reason", 2000),
        (packet.issue.minimal_reproduction, "issue.minimal_reproduction", 2000),
        (packet.issue.proposed_correction, "issue.proposed_correction", 2000),
    ]
    if isinstance(packet, FeedbackPacketV2):
        text_fields.append(
            (
                packet.codemesh.binding.diagnostic_code,
                "codemesh.binding.diagnostic_code",
                120,
            )
        )
        sequences = [event.sequence for event in packet.task.recent_tool_events]
        if sequences != sorted(set(sequences)):
            raise ValueError(
                "Feedback tool-trace sequences must be unique and ordered."
            )
        for event in packet.task.recent_tool_events:
            _safe_text(event.tool, "task.recent_tool_events.tool", 120)
            if event.diagnostic_code is not None:
                _safe_optional_name(
                    event.diagnostic_code,
                    "task.recent_tool_events.diagnostic_code",
                )
    else:
        for name in [*packet.task.tools_attempted, *packet.task.tools_called]:
            _safe_text(name, "task.tools", 120)
    for value, field, maximum in text_fields:
        if value is not None:
            _safe_text(value, field, maximum)
    languages = sorted(
        {
            _safe_text(value, "codemesh.languages", 40).lower()
            for value in packet.codemesh.languages
        }
    )
    if languages != packet.codemesh.languages:
        raise ValueError("codemesh.languages must be lowercase, sorted, and unique.")
    path_fields = {
        "helpful_paths": packet.result.helpful_paths,
        "incorrect_paths": packet.result.incorrect_paths,
        "missed_paths": packet.result.missed_paths,
        "stale_paths": packet.result.stale_paths,
        "ambiguous_paths": packet.result.ambiguous_paths,
        "expected_targets": packet.issue.expected_targets,
    }
    for field, values in path_fields.items():
        if _safe_paths(values, root, field) != values:
            raise ValueError(f"{field} must be sorted and unique.")
    if _safe_feedback_ids(packet.issue.supersedes_feedback_ids) != (
        packet.issue.supersedes_feedback_ids
    ):
        raise ValueError("supersedes_feedback_ids must be sorted and unique.")


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


def _validate_outbox(root: Path, outbox: Path) -> None:
    if outbox.is_symlink() or outbox.is_junction() or outbox.resolve() != outbox:
        raise ValueError("Feedback outbox must be a local directory in the checkout.")
    _require_ignored_outbox(root)


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


def _safe_text_list(
    values: list[str], field: str, maximum: int, maximum_items: int
) -> list[str]:
    if len(values) > maximum_items:
        raise ValueError(f"{field} exceeds {maximum_items} items.")
    return sorted({_safe_text(value, field, maximum) for value in values})


def _safe_optional_name(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    text = _safe_text(value, field, 120)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,119}", text):
        raise ValueError(f"{field} contains unsupported characters.")
    return text


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


def _hash_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None


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


def _priority_score(category: str, members: list[FeedbackPacketType]) -> int:
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
