from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


SCHEMA_VERSION = "1.0"


class RetrievalTarget(BaseModel):
    stable_key: str | None = None
    file_path: str | None = None
    node_id: str | None = None
    relevance: int = Field(default=3, ge=1, le=3)
    primary: bool = False

    @model_validator(mode="after")
    def require_selector(self) -> "RetrievalTarget":
        if not any((self.stable_key, self.file_path, self.node_id)):
            raise ValueError(
                "A retrieval target requires stable_key, file_path, or node_id."
            )
        return self


class RelationshipTarget(BaseModel):
    group: Literal[
        "callers", "callees", "reads", "writes", "contains", "defines", "uses_types"
    ]
    target: RetrievalTarget


class RetrievalCase(BaseModel):
    id: str
    description: str
    tool: Literal[
        "codemesh_get_tool_guidance",
        "codemesh_search_context",
        "codemesh_get_context_package",
        "codemesh_search_symbols",
        "codemesh_get_repository_status",
    ]
    arguments: dict[str, Any] = Field(default_factory=dict)
    targets: list[RetrievalTarget] = Field(default_factory=list)
    relationship_targets: list[RelationshipTarget] = Field(default_factory=list)
    expected_values: dict[str, Any] = Field(default_factory=dict)
    forbidden_substrings: list[str] = Field(default_factory=list)
    min_hit_count: int = Field(default=0, ge=0)
    top_k: int = Field(default=8, ge=1)


class LiveThresholds(BaseModel):
    min_tool_success_rate: float = Field(default=1.0, ge=0, le=1)
    min_recall_at_k: float = Field(default=0.85, ge=0, le=1)
    min_mrr: float = Field(default=0.75, ge=0, le=1)
    max_primary_rank: int = Field(default=3, ge=1)
    max_secret_leaks: int = Field(default=0, ge=0)


class LiveSuite(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    kind: Literal["live"] = "live"
    name: str
    description: str = ""
    repository_id: str = "code_mesh"
    cases: list[RetrievalCase]
    thresholds: LiveThresholds = Field(default_factory=LiveThresholds)


class ValidationCommand(BaseModel):
    argv: list[str] = Field(min_length=1)
    cwd: str = "."
    timeout_seconds: int = Field(default=300, ge=1)


class AgentTask(BaseModel):
    id: str
    description: str
    task_type: Literal["answer", "change"]
    prompt: str
    targets: list[RetrievalTarget] = Field(default_factory=list)
    setup_patch: str | None = None
    validation: list[ValidationCommand] = Field(default_factory=list)
    required_changed_paths: list[str] = Field(default_factory=list)
    allowed_changed_paths: list[str] = Field(default_factory=list)
    forbidden_changed_paths: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=900, ge=1)

    @model_validator(mode="after")
    def validate_task_shape(self) -> "AgentTask":
        if self.task_type == "answer" and not self.targets:
            raise ValueError("Answer tasks require at least one retrieval target.")
        if self.task_type == "change" and (not self.setup_patch or not self.validation):
            raise ValueError(
                "Change tasks require setup_patch and validation commands."
            )
        return self


class AgentThresholds(BaseModel):
    efficiency_delta: float = Field(default=0.10, gt=0, lt=1)
    minimum_completed_pairs: int = Field(default=3, ge=1)


class AgentSuite(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    kind: Literal["agent"] = "agent"
    name: str
    description: str = ""
    repository_id: str = "code_mesh"
    tasks: list[AgentTask]
    thresholds: AgentThresholds = Field(default_factory=AgentThresholds)


class CandidateRecord(BaseModel):
    stable_key: str | None = None
    file_path: str | None = None
    node_id: str | None = None


class LiveCaseReport(BaseModel):
    id: str
    tool: str
    passed: bool
    calls: int
    successful_calls: int
    latencies_ms: list[float] = Field(default_factory=list)
    p50_latency_ms: float = 0
    p95_latency_ms: float = 0
    hit_count: int = 0
    precision_at_k: float = 0
    recall_at_k: float = 0
    reciprocal_rank: float = 0
    ndcg_at_k: float = 0
    ranking_stability: float = 0
    relationship_coverage: float = 0
    primary_rank: int | None = None
    secret_leaks: int = 0
    candidates: list[CandidateRecord] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    failures: list[str] = Field(default_factory=list)
    raw_responses: list[dict[str, Any]] | None = None


class LiveReport(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    kind: Literal["live-report"] = "live-report"
    suite: str
    passed: bool
    comparable: bool
    generated_at: str
    duration_ms: float
    startup_ms: float
    repository_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    cases: list[LiveCaseReport] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


class AgentExecutionReport(BaseModel):
    task_id: str
    repetition: int
    condition: Literal["control", "treatment"]
    completed: bool
    passed: bool
    safety_violation: bool = False
    duration_ms: float = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    mcp_calls: list[str] = Field(default_factory=list)
    command_count: int = 0
    file_change_count: int = 0
    changed_paths: list[str] = Field(default_factory=list)
    validation: list[dict[str, Any]] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    sanitized_diff: str | None = None
    raw_events: list[dict[str, Any]] | None = None
    final_message: str | None = None


class AgentReport(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    kind: Literal["agent-report"] = "agent-report"
    suite: str
    model: str
    reasoning_effort: str
    seed: int
    repetitions: int
    generated_at: str
    duration_ms: float
    verdict: Literal["improved", "regressed", "neutral", "insufficient"]
    passed: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    runs: list[AgentExecutionReport] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


Suite = LiveSuite | AgentSuite


def built_in_suite_path(name: str) -> Path:
    path = Path(__file__).with_name("suites") / f"{name}.json"
    if not path.is_file():
        raise ValueError(f"Unknown built-in evaluation suite '{name}'.")
    return path


def load_suite(
    value: str | Path, expected_kind: str | None = None
) -> tuple[Suite, Path]:
    candidate = Path(value)
    path = candidate if candidate.is_file() else built_in_suite_path(str(value))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load evaluation suite '{path}': {exc}") from exc

    kind = payload.get("kind")
    if expected_kind and kind != expected_kind:
        raise ValueError(f"Expected a {expected_kind} suite, but '{path}' is '{kind}'.")
    if kind == "live":
        return LiveSuite.model_validate(payload), path
    if kind == "agent":
        return AgentSuite.model_validate(payload), path
    raise ValueError(f"Evaluation suite '{path}' has unsupported kind '{kind}'.")


def suite_json_schema(kind: Literal["live", "agent"]) -> dict[str, Any]:
    model = LiveSuite if kind == "live" else AgentSuite
    return model.model_json_schema()
