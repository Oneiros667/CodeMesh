from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field, model_validator

from .paths import (
    ARTIFACT_ID_PATTERN,
    resolve_setup_patch,
    validate_artifact_id,
    validate_setup_patch_name,
)


SCHEMA_VERSION = "1.0"
MODEL_BENCHMARK_SCHEMA_VERSION = "1.0"

Difficulty = Literal["easy", "medium", "hard"]
AgentIntegrationMode = Literal["spontaneous", "assisted", "configured"]
ArtifactId = Annotated[
    str, Field(pattern=ARTIFACT_ID_PATTERN), AfterValidator(validate_artifact_id)
]
SetupPatchPath = Annotated[str, AfterValidator(validate_setup_patch_name)]


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
    repository_url: str | None = None
    repository_commit: str | None = None
    cases: list[RetrievalCase]
    thresholds: LiveThresholds = Field(default_factory=LiveThresholds)


class ValidationCommand(BaseModel):
    argv: list[str] = Field(min_length=1)
    cwd: str = "."
    timeout_seconds: int = Field(default=300, ge=1)


class CommandPolicy(BaseModel):
    max_commands: int = Field(default=50, ge=0)
    forbidden_substrings: list[str] = Field(
        default_factory=lambda: [
            "rm -rf",
            "git reset --hard",
            "git clean -",
            "sudo ",
            ".env",
        ]
    )


class AgentTask(BaseModel):
    id: ArtifactId
    description: str
    task_type: Literal["answer", "change"]
    prompt: str
    targets: list[RetrievalTarget] = Field(default_factory=list)
    setup_patch: SetupPatchPath | None = None
    validation: list[ValidationCommand] = Field(default_factory=list)
    required_changed_paths: list[str] = Field(default_factory=list)
    allowed_changed_paths: list[str] = Field(default_factory=list)
    forbidden_changed_paths: list[str] = Field(default_factory=list)
    command_policy: CommandPolicy | None = None
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
    name: ArtifactId
    description: str = ""
    repository_id: str = "code_mesh"
    repository_url: str | None = None
    repository_commit: str | None = None
    integration_mode: AgentIntegrationMode | None = None
    baseline_mcp_servers: list[str] = Field(default_factory=list)
    treatment_guidance: str | None = None
    tasks: list[AgentTask]
    thresholds: AgentThresholds = Field(default_factory=AgentThresholds)

    @model_validator(mode="after")
    def validate_integration_mode(self) -> "AgentSuite":
        _require_unique_artifact_ids(self.tasks)
        if self.integration_mode == "configured" and self.treatment_guidance:
            raise ValueError(
                "Configured agent suites must use shipped repository guidance, "
                "not evaluator-only treatment guidance."
            )
        if self.integration_mode == "configured" and not self.repository_commit:
            raise ValueError(
                "Configured agent suites require a pinned repository commit."
            )
        if self.baseline_mcp_servers and self.integration_mode != "configured":
            raise ValueError(
                "Baseline MCP servers can be selected only by configured suites."
            )
        normalized_servers = [value.strip() for value in self.baseline_mcp_servers]
        if any(not value for value in normalized_servers) or len(
            set(normalized_servers)
        ) != len(normalized_servers):
            raise ValueError("Baseline MCP server names must be non-empty and unique.")
        if any(
            re.fullmatch(r"[A-Za-z0-9_-]+", value) is None
            for value in normalized_servers
        ):
            raise ValueError(
                "Baseline MCP server names may contain only letters, digits, "
                "underscores, and hyphens."
            )
        self.baseline_mcp_servers = normalized_servers
        if self.integration_mode == "assisted" and not self.treatment_guidance:
            raise ValueError(
                "Assisted agent suites require evaluator treatment guidance."
            )
        if self.integration_mode == "spontaneous" and self.treatment_guidance:
            raise ValueError(
                "Spontaneous agent suites cannot include treatment guidance."
            )
        return self

    @property
    def resolved_integration_mode(self) -> AgentIntegrationMode:
        if self.integration_mode is not None:
            return self.integration_mode
        return "assisted" if self.treatment_guidance else "spontaneous"


class CriterionWeights(BaseModel):
    accuracy: int = Field(default=35, ge=0, le=100)
    instruction_following: int = Field(default=15, ge=0, le=100)
    tool_use: int = Field(default=15, ge=0, le=100)
    safety: int = Field(default=10, ge=0, le=100)
    insight: int = Field(default=10, ge=0, le=100)
    reliability: int = Field(default=5, ge=0, le=100)
    token_efficiency: int = Field(default=5, ge=0, le=100)
    speed: int = Field(default=5, ge=0, le=100)

    @model_validator(mode="after")
    def require_total(self) -> "CriterionWeights":
        if sum(self.model_dump().values()) != 100:
            raise ValueError("Model benchmark criterion weights must total 100.")
        return self


class ToolPolicy(BaseModel):
    allowed_tools: list[str] = Field(min_length=1)
    max_calls: int = Field(ge=1)
    required_sequence: list[str] = Field(default_factory=list)
    per_tool_limits: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policy(self) -> "ToolPolicy":
        allowed = set(self.allowed_tools)
        if any(tool not in allowed for tool in self.required_sequence):
            raise ValueError("Required tool sequence contains a non-allowed tool.")
        if any(tool not in allowed for tool in self.per_tool_limits):
            raise ValueError("Per-tool limits contain a non-allowed tool.")
        if any(limit < 1 for limit in self.per_tool_limits.values()):
            raise ValueError("Per-tool limits must be positive.")
        if len(self.required_sequence) > self.max_calls:
            raise ValueError("Required tool sequence exceeds max_calls.")
        return self


class HumanRubric(BaseModel):
    invariants: str
    edge_cases: str
    uncertainty: str
    implications: str


class BenchmarkQuestion(BaseModel):
    id: ArtifactId
    family_id: str
    difficulty: Difficulty
    description: str
    prompt: str
    targets: list[RetrievalTarget] = Field(min_length=1)
    expected_facts: dict[str, Any] = Field(min_length=1)
    forbidden_substrings: list[str] = Field(default_factory=list)
    tool_policy: ToolPolicy
    human_rubric: HumanRubric
    timeout_seconds: int = Field(default=900, ge=1)


class BenchmarkChangeScenario(BaseModel):
    id: ArtifactId
    family_id: str
    difficulty: Difficulty
    description: str
    prompt: str
    setup_patch: SetupPatchPath
    validation: list[ValidationCommand] = Field(min_length=1)
    required_changed_paths: list[str] = Field(min_length=1)
    allowed_changed_paths: list[str] = Field(min_length=1)
    forbidden_changed_paths: list[str] = Field(default_factory=list)
    command_policy: CommandPolicy = Field(default_factory=CommandPolicy)
    expected_facts: dict[str, Any] = Field(min_length=1)
    tool_policy: ToolPolicy
    human_rubric: HumanRubric
    timeout_seconds: int = Field(default=900, ge=1)


class ModelBenchmarkThresholds(BaseModel):
    query_score: float = Field(default=75, ge=0, le=100)
    change_score: float = Field(default=70, ge=0, le=100)
    query_minimums: dict[Difficulty, int] = Field(
        default_factory=lambda: {"easy": 7, "medium": 6, "hard": 4}
    )
    change_minimums: dict[Difficulty, int] = Field(
        default_factory=lambda: {"easy": 2, "medium": 2, "hard": 2}
    )
    minimum_repetitions: int = Field(default=3, ge=3)


class ModelBenchmarkSuite(BaseModel):
    schema_version: Literal["1.0"] = MODEL_BENCHMARK_SCHEMA_VERSION
    kind: Literal["model-benchmark"] = "model-benchmark"
    name: ArtifactId
    description: str = ""
    repository_id: str = "code_mesh"
    weights: CriterionWeights = Field(default_factory=CriterionWeights)
    thresholds: ModelBenchmarkThresholds = Field(
        default_factory=ModelBenchmarkThresholds
    )
    questions: list[BenchmarkQuestion]
    change_scenarios: list[BenchmarkChangeScenario]

    @model_validator(mode="after")
    def validate_matrix(self) -> "ModelBenchmarkSuite":
        _require_unique_artifact_ids([*self.questions, *self.change_scenarios])
        _require_difficulty_matrix(self.questions, family_count=8, label="question")
        _require_difficulty_matrix(
            self.change_scenarios, family_count=3, label="change scenario"
        )
        if len(self.questions) != 24:
            raise ValueError("Model benchmark requires exactly 24 query questions.")
        if len(self.change_scenarios) != 9:
            raise ValueError("Model benchmark requires exactly 9 change scenarios.")
        return self


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
    reported_tokens: int = 0
    reported_token_limit: int | None = None
    mcp_calls: list[str] = Field(default_factory=list)
    mcp_call_attempts: list[str] = Field(default_factory=list)
    mcp_failed_calls: list[str] = Field(default_factory=list)
    command_count: int = 0
    command_policy_violations: list[str] = Field(default_factory=list)
    file_change_count: int = 0
    changed_paths: list[str] = Field(default_factory=list)
    validation: list[dict[str, Any]] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    sanitized_diff: str | None = None
    raw_events: list[dict[str, Any]] | None = None
    final_message: str | None = None
    hard_cap_ledger: dict[str, Any] | None = None


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


class BenchmarkCitation(BaseModel):
    file_path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    stable_key: str | None = None


class BenchmarkRunReport(BaseModel):
    scenario_id: str
    family_id: str
    difficulty: Difficulty
    tier: Literal["query", "change"]
    repetition: int
    condition: Literal["control", "treatment"]
    completed: bool
    passed: bool
    safety_violation: bool = False
    duration_ms: float = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[str] = Field(default_factory=list)
    blocked_tool_calls: list[str] = Field(default_factory=list)
    answer: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    citations: list[BenchmarkCitation] = Field(default_factory=list)
    changed_paths: list[str] = Field(default_factory=list)
    validation: list[dict[str, Any]] = Field(default_factory=list)
    sanitized_diff: str | None = None
    criterion_scores: dict[str, float | None] = Field(default_factory=dict)
    weighted_score: float | None = None
    failures: list[str] = Field(default_factory=list)
    raw_events: list[dict[str, Any]] | None = None


class ModelBenchmarkReport(BaseModel):
    schema_version: Literal["1.0"] = MODEL_BENCHMARK_SCHEMA_VERSION
    kind: Literal["model-benchmark-report"] = "model-benchmark-report"
    suite: str
    model: str
    tier: Literal["query", "change", "all"]
    seed: int
    repetitions: int
    generated_at: str
    status: Literal["provisional", "reviewed", "compared"] = "provisional"
    qualified: bool = False
    certified: bool = False
    comparable: bool = True
    query_score: float | None = None
    change_score: float | None = None
    final_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    runs: list[BenchmarkRunReport] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


class InsightReview(BaseModel):
    anonymous_id: str
    score: float = Field(ge=0, le=4)
    reviewer_id: str
    notes: str = ""


class ReviewFile(BaseModel):
    schema_version: Literal["1.0"] = MODEL_BENCHMARK_SCHEMA_VERSION
    reviews: list[InsightReview]


class ModelComparisonReport(BaseModel):
    schema_version: Literal["1.0"] = MODEL_BENCHMARK_SCHEMA_VERSION
    kind: Literal["model-comparison-report"] = "model-comparison-report"
    generated_at: str
    comparable: bool
    rankings: list[dict[str, Any]]
    failures: list[str] = Field(default_factory=list)


Suite = LiveSuite | AgentSuite | ModelBenchmarkSuite


def built_in_suite_path(name: str) -> Path:
    validate_artifact_id(name)
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
        suite = AgentSuite.model_validate(payload)
    elif kind == "model-benchmark":
        suite = ModelBenchmarkSuite.model_validate(payload)
    else:
        raise ValueError(f"Evaluation suite '{path}' has unsupported kind '{kind}'.")
    validate_suite_artifacts(suite, path)
    return suite, path


def validate_suite_artifacts(
    suite: AgentSuite | ModelBenchmarkSuite, suite_path: Path
) -> None:
    validate_artifact_id(suite.name)
    items = (
        suite.tasks
        if isinstance(suite, AgentSuite)
        else [*suite.questions, *suite.change_scenarios]
    )
    _require_unique_artifact_ids(items)
    for item in items:
        validate_artifact_id(item.id)
        if patch := getattr(item, "setup_patch", None):
            resolve_setup_patch(suite_path, patch)


def _require_unique_artifact_ids(items: list[Any]) -> None:
    identifiers = [item.id.casefold() for item in items]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Evaluation identifiers must be unique ignoring case.")


def suite_json_schema(kind: Literal["live", "agent", "model"]) -> dict[str, Any]:
    model = (
        LiveSuite
        if kind == "live"
        else AgentSuite
        if kind == "agent"
        else ModelBenchmarkSuite
    )
    return model.model_json_schema()


def _require_difficulty_matrix(
    items: list[Any], *, family_count: int, label: str
) -> None:
    families: dict[str, set[str]] = {}
    for item in items:
        family = families.setdefault(item.family_id, set())
        if item.difficulty in family:
            raise ValueError(
                f"Duplicate {label} difficulty '{item.difficulty}' in family '{item.family_id}'."
            )
        family.add(item.difficulty)
    if len(families) != family_count:
        raise ValueError(
            f"Model benchmark requires exactly {family_count} {label} families."
        )
    expected = {"easy", "medium", "hard"}
    incomplete = [
        name for name, difficulties in families.items() if difficulties != expected
    ]
    if incomplete:
        raise ValueError(
            f"Every {label} family requires easy, medium, and hard variants: {', '.join(sorted(incomplete))}."
        )
