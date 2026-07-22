from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from codemesh_agent_access.evaluation.agent import (
    _grade_answer,
    _grade_command_policy,
    _run_task_condition,
    classify_agent_results,
)
from codemesh_agent_access.evaluation.codex import (
    AgentRunRequest,
    AgentRunResult,
    CodexRunner,
    parse_codex_jsonl,
    sanitize_text,
)
from codemesh_agent_access.evaluation.live import (
    EvaluationInfrastructureError,
    McpEvaluationClient,
    _run_live_case,
)
from codemesh_agent_access.evaluation.metrics import (
    percentile,
    ranking_metrics,
    ranking_stability,
)
from codemesh_agent_access.evaluation.models import (
    AgentExecutionReport,
    AgentSuite,
    AgentTask,
    CandidateRecord,
    CommandPolicy,
    RetrievalCase,
    RetrievalTarget,
    ValidationCommand,
    load_suite,
    suite_json_schema,
)


def test_built_in_suites_and_schemas_are_valid() -> None:
    live, live_path = load_suite("codemesh-live", "live")
    agent, agent_path = load_suite("codemesh-agent", "agent")
    model, model_path = load_suite("codemesh-model", "model-benchmark")

    assert live.name == "codemesh-live"
    assert len(live.cases) >= 9
    assert agent.name == "codemesh-agent"
    assert {task.task_type for task in agent.tasks} == {"answer", "change"}
    assert model.name == "codemesh-model"
    assert len(model.questions) == 24
    assert len(model.change_scenarios) == 9
    assert live_path.is_file()
    assert agent_path.is_file()
    assert model_path.is_file()
    assert suite_json_schema("live")["title"] == "LiveSuite"
    assert suite_json_schema("agent")["title"] == "AgentSuite"
    assert suite_json_schema("model")["title"] == "ModelBenchmarkSuite"


def test_built_in_fault_patches_apply_to_current_head() -> None:
    _suite, suite_path = load_suite("codemesh-agent", "agent")
    repository = Path(__file__).resolve().parents[2]

    for patch in sorted((suite_path.parent / "patches").glob("*.patch")):
        result = subprocess.run(
            ["git", "-C", str(repository), "apply", "--check", str(patch)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{patch.name}: {result.stderr}"


def test_suite_models_reject_incomplete_targets_and_change_tasks() -> None:
    with pytest.raises(ValidationError):
        RetrievalTarget()

    with pytest.raises(ValidationError):
        AgentTask(
            id="broken",
            description="broken",
            task_type="change",
            prompt="fix it",
        )


def test_ranking_metrics_and_stability_are_deterministic() -> None:
    candidates = [
        CandidateRecord(file_path="src/Other.cs"),
        CandidateRecord(file_path="src/Primary.cs"),
        CandidateRecord(file_path="src/Secondary.cs"),
    ]
    targets = [
        RetrievalTarget(file_path="src/Primary.cs", relevance=3, primary=True),
        RetrievalTarget(file_path="src/Secondary.cs", relevance=2),
    ]

    metrics = ranking_metrics(candidates, targets, 3)

    assert metrics["precision_at_k"] == pytest.approx(2 / 3)
    assert metrics["recall_at_k"] == 1
    assert metrics["reciprocal_rank"] == 0.5
    assert metrics["primary_rank"] == 2
    assert 0 < float(metrics["ndcg_at_k"]) < 1
    assert ranking_stability([candidates, list(candidates)]) == 1
    assert ranking_stability([candidates, list(reversed(candidates))]) == 0
    assert percentile([10, 20, 30, 40], 0.95) == 40


def test_ranking_metrics_count_a_file_target_only_once() -> None:
    candidates = [
        CandidateRecord(file_path="src/Target.cs", node_id="node:one"),
        CandidateRecord(file_path="src/Target.cs", node_id="node:two"),
    ]
    targets = [RetrievalTarget(file_path="src/Target.cs", relevance=3)]

    metrics = ranking_metrics(candidates, targets, 2)

    assert metrics["precision_at_k"] == 0.5
    assert metrics["recall_at_k"] == 1
    assert metrics["ndcg_at_k"] == 1


def test_mcp_client_accepts_structured_payload_and_rejects_non_json() -> None:
    class FakeSession:
        def __init__(self, result: Any) -> None:
            self.result = result

        async def call_tool(self, *_args: Any, **_kwargs: Any) -> Any:
            return self.result

    client = McpEvaluationClient()
    client.session = FakeSession(
        SimpleNamespace(
            isError=False,
            structuredContent={"ok": True, "data": {"hits": []}},
            content=[],
        )
    )  # type: ignore[assignment]
    payload, latency = asyncio.run(client.call("codemesh_search_context", {}))
    assert payload["ok"] is True
    assert latency >= 0

    client.session = FakeSession(
        SimpleNamespace(
            isError=False,
            structuredContent=None,
            content=[SimpleNamespace(text="not json")],
        )
    )  # type: ignore[assignment]
    with pytest.raises(EvaluationInfrastructureError):
        asyncio.run(client.call("codemesh_search_context", {}))


def test_live_case_scores_results_and_omits_raw_payloads() -> None:
    class FakeClient:
        async def call(
            self, _tool: str, _arguments: dict[str, Any]
        ) -> tuple[dict[str, Any], float]:
            return (
                {
                    "ok": True,
                    "data": {
                        "hits": [
                            {
                                "node_id": "node:target",
                                "stable_key": "Target",
                                "file_path": "src/Target.cs",
                            }
                        ],
                        "diagnostics": {"mode": "lexical"},
                    },
                },
                12.5,
            )

    case = RetrievalCase(
        id="target",
        description="target",
        tool="codemesh_search_context",
        arguments={"query": "target"},
        targets=[RetrievalTarget(file_path="src/Target.cs", primary=True, relevance=3)],
        min_hit_count=1,
    )
    report = asyncio.run(
        _run_live_case(FakeClient(), case, case.arguments, 3, False, 3)  # type: ignore[arg-type]
    )

    assert report.passed is True, report.failures
    assert report.recall_at_k == 1
    assert report.primary_rank == 1
    assert report.ranking_stability == 1
    assert report.raw_responses is None

    raw_report = asyncio.run(
        _run_live_case(FakeClient(), case, case.arguments, 1, True, 3)  # type: ignore[arg-type]
    )
    assert raw_report.raw_responses is not None


def test_codex_jsonl_parser_collects_usage_tools_and_failures() -> None:
    stream = "\n".join(
        [
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "rg target src",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "item.started",
                    "item": {
                        "type": "mcp_tool_call",
                        "server": "codemesh",
                        "tool": "codemesh_search_context",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": '{"answer":"ok","citations":[]}',
                    },
                }
            ),
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 20, "output_tokens": 5},
                }
            ),
            "malformed",
        ]
    )

    result = parse_codex_jsonl(stream)

    assert result.completed is True
    assert result.usage["input_tokens"] == 20
    assert result.mcp_calls == ["codemesh.codemesh_search_context"]
    assert result.mcp_call_attempts == ["codemesh.codemesh_search_context"]
    assert result.commands == ["rg target src"]
    assert result.final_message.startswith("{")
    assert "malformed JSONL" in result.failures[0]


def test_answer_grading_validates_target_and_line_range(tmp_path: Path) -> None:
    source = tmp_path / "src" / "Target.cs"
    source.parent.mkdir()
    source.write_text("line one\nline two\n", encoding="utf-8")
    target = RetrievalTarget(file_path="src/Target.cs")
    valid = json.dumps(
        {
            "answer": "answer",
            "citations": [
                {
                    "file_path": "src/Target.cs",
                    "start_line": 1,
                    "end_line": 2,
                    "stable_key": None,
                }
            ],
        }
    )
    invalid = valid.replace('"end_line": 2', '"end_line": 20')

    assert _grade_answer(valid, [target], tmp_path) == []
    assert "outside the file" in _grade_answer(invalid, [target], tmp_path)[0]


def test_codex_arguments_only_enable_codemesh_for_treatment(tmp_path: Path) -> None:
    runner = CodexRunner()
    common = {
        "prompt": "task",
        "cwd": tmp_path,
        "model": "test-model",
        "reasoning_effort": "medium",
        "sandbox": "read-only",
        "timeout_seconds": 60,
        "mcp_cwd": tmp_path,
    }
    control = runner._arguments(AgentRunRequest(condition="control", **common))
    treatment = runner._arguments(AgentRunRequest(condition="treatment", **common))

    assert "mcp_servers={}" in control
    assert 'mcp_servers.codemesh.command="uv"' in treatment
    assert "mcp_servers.codemesh.required=true" in treatment
    assert any(
        value.startswith("mcp_servers.codemesh.enabled_tools=") for value in treatment
    )
    assert not any("codemesh_delete_repository" in value for value in treatment)
    assert "--ephemeral" in treatment
    assert "--ignore-user-config" in treatment

    legacy = runner._arguments(
        AgentRunRequest(condition="treatment", **common),
        supports_ignore_user_config=False,
    )
    assert "--ignore-user-config" not in legacy

    local = runner._arguments(
        AgentRunRequest(condition="control", local_provider="lmstudio", **common)
    )
    assert local[local.index("--local-provider") + 1] == "lmstudio"
    assert "--oss" in local


def test_agent_classifier_prioritizes_correctness_and_safety() -> None:
    suite = AgentSuite(
        name="agent",
        tasks=[
            AgentTask(
                id="answer",
                description="answer",
                task_type="answer",
                prompt="answer",
                targets=[RetrievalTarget(file_path="src/A.cs")],
            )
        ],
    )
    runs = []
    for repetition in range(1, 4):
        runs.extend(
            [
                AgentExecutionReport(
                    task_id="answer",
                    repetition=repetition,
                    condition="control",
                    completed=True,
                    passed=False,
                    duration_ms=100,
                ),
                AgentExecutionReport(
                    task_id="answer",
                    repetition=repetition,
                    condition="treatment",
                    completed=True,
                    passed=True,
                    duration_ms=120,
                    mcp_calls=["codemesh.search"],
                ),
            ]
        )

    verdict, summary = classify_agent_results(runs, suite)
    assert verdict == "improved"
    assert summary["treatment_wins"] == 3
    assert summary["codemesh_adoption_rate"] == 1

    runs[-1].safety_violation = True
    verdict, _summary = classify_agent_results(runs, suite)
    assert verdict == "regressed"


def test_command_policy_rejects_unsafe_commands() -> None:
    task = AgentTask(
        id="change",
        description="change",
        task_type="change",
        prompt="change",
        setup_patch="fault.patch",
        validation=[ValidationCommand(argv=["true"])],
    )
    task.command_policy = CommandPolicy(
        max_commands=1,
        forbidden_substrings=["git reset --hard"],
    )

    failures = _grade_command_policy(task, ["git reset --hard HEAD", "dotnet test"])

    assert any("maximum" in failure for failure in failures)
    assert any("git reset --hard" in failure for failure in failures)


def test_change_task_runs_in_an_isolated_clone(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "value.txt").write_text("good\n", encoding="utf-8")
    _git(repository, "init", "--quiet")
    _git(repository, "config", "user.name", "CodeMesh Test")
    _git(repository, "config", "user.email", "codemesh@example.invalid")
    _git(repository, "add", "value.txt")
    _git(repository, "commit", "--quiet", "-m", "fixture")
    base_commit = _git(repository, "rev-parse", "HEAD").strip()

    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    suite_path = suite_dir / "suite.json"
    suite_path.write_text("{}", encoding="utf-8")
    patch_path = suite_dir / "fault.patch"
    patch_path.write_text(
        """diff --git a/value.txt b/value.txt
--- a/value.txt
+++ b/value.txt
@@ -1 +1 @@
-good
+bad
""",
        encoding="utf-8",
    )

    task = AgentTask(
        id="repair",
        description="repair",
        task_type="change",
        prompt="repair value",
        setup_patch="fault.patch",
        validation=[
            ValidationCommand(
                argv=[
                    "python",
                    "-c",
                    "import pathlib,sys;sys.exit(pathlib.Path('value.txt').read_text().strip()!='good')",
                ]
            )
        ],
        required_changed_paths=["value.txt"],
        allowed_changed_paths=["value.txt"],
    )

    class FakeRunner:
        async def run(self, request: AgentRunRequest) -> AgentRunResult:
            (request.cwd / "value.txt").write_text("good\n", encoding="utf-8")
            return AgentRunResult(
                completed=True,
                exit_code=0,
                duration_ms=10,
                usage={"input_tokens": 5, "output_tokens": 2},
            )

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    report = asyncio.run(
        _run_task_condition(
            suite_path=suite_path,
            task=task,
            repetition=1,
            condition="treatment",
            root=repository,
            base_commit=base_commit,
            model="test",
            local_provider=None,
            reasoning_effort="medium",
            mcp_cwd=tmp_path,
            keep_raw_traces=False,
            keep_workspaces=False,
            runner=FakeRunner(),
            artifact_dir=artifacts,
        )
    )

    assert report.passed is True, report.failures
    assert report.changed_paths == ["value.txt"]
    assert (repository / "value.txt").read_text(encoding="utf-8") == "good\n"


def test_artifact_sanitizer_redacts_secret_values() -> None:
    text = "CODEMESH_TOKEN=do-not-store password: hunter2"
    sanitized = sanitize_text(text)

    assert "do-not-store" not in sanitized
    assert "hunter2" not in sanitized
    assert sanitized.count("[REDACTED]") == 2


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout
