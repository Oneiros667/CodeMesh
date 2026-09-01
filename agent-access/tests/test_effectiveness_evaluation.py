from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

import codemesh_agent_access.evaluation.agent as agent_evaluation
from codemesh_agent_access.binding import RepositoryBinding
from codemesh_agent_access.evaluation.agent import (
    AgentEvaluationContext,
    ConfiguredGuidanceFile,
    _condition_prompt,
    _grade_answer,
    _grade_command_policy,
    _prepare_agent_context,
    _prepare_configured_integration,
    _run_task_condition,
    classify_agent_results,
    run_agent_evaluation,
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
    get_repository_preflight,
    get_tool_source_identity,
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
from codemesh_agent_access.installer import (
    apply_installation_plan,
    create_installation_plan,
)


def test_built_in_suites_and_schemas_are_valid() -> None:
    live, live_path = load_suite("codemesh-live", "live")
    external_live, external_live_path = load_suite("youtube-downloader-live", "live")
    impact_live, impact_live_path = load_suite("youtube-downloader-impact-live", "live")
    agent, agent_path = load_suite("codemesh-agent", "agent")
    external_agent, external_agent_path = load_suite(
        "youtube-downloader-agent", "agent"
    )
    impact_agent, impact_agent_path = load_suite(
        "youtube-downloader-impact-agent", "agent"
    )
    assisted_agent, assisted_agent_path = load_suite(
        "youtube-downloader-impact-assisted-agent", "agent"
    )
    configured_impact_agent, configured_impact_agent_path = load_suite(
        "youtube-downloader-impact-configured-agent", "agent"
    )
    independent_live, independent_live_path = load_suite(
        "config-net-cache-live", "live"
    )
    independent_focused_live, independent_focused_live_path = load_suite(
        "config-net-cache-focused-live", "live"
    )
    independent_agent, independent_agent_path = load_suite(
        "config-net-cache-agent", "agent"
    )
    independent_assisted_agent, independent_assisted_agent_path = load_suite(
        "config-net-cache-assisted-agent", "agent"
    )
    independent_configured_agent, independent_configured_agent_path = load_suite(
        "config-net-cache-configured-agent", "agent"
    )
    onenine_configured_agent, onenine_configured_agent_path = load_suite(
        "onenine-native-replay-configured-agent", "agent"
    )
    model, model_path = load_suite("codemesh-model", "model-benchmark")

    assert live.name == "codemesh-live"
    assert len(live.cases) >= 9
    assert external_live.repository_id == "youtube_downloader"
    assert external_live.repository_commit
    assert len(impact_live.cases) == 2
    assert impact_live.repository_commit == external_live.repository_commit
    assert agent.name == "codemesh-agent"
    assert {task.task_type for task in agent.tasks} == {"answer", "change"}
    assert len(external_agent.tasks) == 3
    assert external_agent.repository_commit == external_live.repository_commit
    assert len(impact_agent.tasks) == 1
    assert impact_agent.repository_commit == external_live.repository_commit
    assert assisted_agent.treatment_guidance
    assert assisted_agent.repository_commit == external_live.repository_commit
    assert configured_impact_agent.resolved_integration_mode == "configured"
    assert configured_impact_agent.repository_commit == external_live.repository_commit
    assert configured_impact_agent.treatment_guidance is None
    assert configured_impact_agent.tasks == impact_agent.tasks
    assert independent_agent.treatment_guidance is None
    assert independent_agent.repository_commit == independent_live.repository_commit
    assert independent_focused_live.repository_commit == (
        independent_live.repository_commit
    )
    assert len(independent_focused_live.cases) == 5
    assert {
        target.file_path
        for case in independent_focused_live.cases
        for target in case.targets
    } == {
        "src/Config.Net/Core/IoHandler.cs",
        "src/Config.Net/Core/LazyVar.cs",
        "src/Config.Net/Core/DynamicWriter.cs",
        "src/Config.Net/Core/InterfaceInterceptor.cs",
        "src/Config.Net/ConfigurationBuilder.cs",
        "src/Config.Net.Tests/LogicTest.cs",
        "src/Config.Net.Tests/ConfigurableMethodsTest.cs",
    }
    assert independent_assisted_agent.treatment_guidance
    assert (
        independent_assisted_agent.repository_commit
        == independent_live.repository_commit
    )
    assert independent_configured_agent.resolved_integration_mode == "configured"
    assert independent_configured_agent.repository_commit == (
        independent_live.repository_commit
    )
    assert independent_configured_agent.treatment_guidance is None
    assert len(independent_configured_agent.tasks) == 1
    assert onenine_configured_agent.resolved_integration_mode == "configured"
    assert onenine_configured_agent.repository_commit == (
        "fe2f761583bf78601961ff17934185c4b6a632f9"
    )
    assert onenine_configured_agent.treatment_guidance is None
    assert len(onenine_configured_agent.tasks) == 1
    assert independent_live.repository_url != external_live.repository_url
    assert model.name == "codemesh-model"
    assert len(model.questions) == 24
    assert len(model.change_scenarios) == 9
    assert live_path.is_file()
    assert external_live_path.is_file()
    assert impact_live_path.is_file()
    assert agent_path.is_file()
    assert external_agent_path.is_file()
    assert impact_agent_path.is_file()
    assert assisted_agent_path.is_file()
    assert configured_impact_agent_path.is_file()
    assert independent_configured_agent_path.is_file()
    assert independent_live_path.is_file()
    assert independent_focused_live_path.is_file()
    assert independent_agent_path.is_file()
    assert independent_assisted_agent_path.is_file()
    assert onenine_configured_agent_path.is_file()
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


def test_agent_suite_integration_modes_preserve_prompt_contracts() -> None:
    task = AgentTask(
        id="answer",
        description="answer",
        task_type="answer",
        prompt="answer",
        targets=[RetrievalTarget(file_path="src/A.cs")],
    )

    assert AgentSuite(name="default", tasks=[task]).resolved_integration_mode == (
        "spontaneous"
    )
    assert (
        AgentSuite(
            name="assisted",
            tasks=[task],
            treatment_guidance="Use CodeMesh first.",
        ).resolved_integration_mode
        == "assisted"
    )
    configured = AgentSuite(
        name="configured",
        tasks=[task],
        integration_mode="configured",
        repository_commit="commit:test",
        baseline_mcp_servers=["graphify"],
    )
    assert configured.resolved_integration_mode == "configured"
    assert configured.baseline_mcp_servers == ["graphify"]
    assert _condition_prompt(task.prompt, "control", None) == task.prompt
    assert _condition_prompt(task.prompt, "treatment", None) == task.prompt

    with pytest.raises(ValidationError, match="shipped repository guidance"):
        AgentSuite(
            name="invalid-configured",
            tasks=[task],
            integration_mode="configured",
            repository_commit="commit:test",
            treatment_guidance="Evaluator-only guidance.",
        )
    with pytest.raises(ValidationError, match="require evaluator treatment guidance"):
        AgentSuite(
            name="invalid-assisted",
            tasks=[task],
            integration_mode="assisted",
        )
    with pytest.raises(ValidationError, match="pinned repository commit"):
        AgentSuite(
            name="unpinned-configured",
            tasks=[task],
            integration_mode="configured",
        )
    with pytest.raises(ValidationError, match="only by configured suites"):
        AgentSuite(
            name="invalid-baseline",
            tasks=[task],
            baseline_mcp_servers=["graphify"],
        )
    with pytest.raises(ValidationError, match="non-empty and unique"):
        AgentSuite(
            name="duplicate-baseline",
            tasks=[task],
            integration_mode="configured",
            repository_commit="commit:test",
            baseline_mcp_servers=["graphify", "graphify"],
        )
    with pytest.raises(ValidationError, match="letters, digits"):
        AgentSuite(
            name="invalid-baseline-name",
            tasks=[task],
            integration_mode="configured",
            repository_commit="commit:test",
            baseline_mcp_servers=["graphify.server"],
        )


def test_agent_context_rejects_dirty_and_stale_candidates(
    monkeypatch: Any, tmp_path: Path
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    tracked = target / "tracked.txt"
    tracked.write_text("clean\n", encoding="utf-8")
    _git(target, "init", "--quiet")
    _git(target, "config", "user.name", "CodeMesh Test")
    _git(target, "config", "user.email", "codemesh@example.invalid")
    _git(target, "add", "tracked.txt")
    _git(target, "commit", "--quiet", "-m", "fixture")
    base_commit = _git(target, "rev-parse", "HEAD").strip()
    suite = AgentSuite(
        name="configured",
        repository_commit=base_commit,
        integration_mode="configured",
        tasks=[
            AgentTask(
                id="answer",
                description="answer",
                task_type="answer",
                prompt="answer",
                targets=[RetrievalTarget(file_path="tracked.txt")],
            )
        ],
    )

    async def stale_preflight(_repository_id: str) -> dict[str, Any]:
        return {
            "freshness": {
                "indexed_commit": "stale",
                "current_commit": base_commit,
                "working_tree_dirty": False,
            }
        }

    tracked.write_text("dirty\n", encoding="utf-8")
    with pytest.raises(EvaluationInfrastructureError, match="clean source checkout"):
        asyncio.run(
            _prepare_agent_context(
                suite,
                repository_root=target,
                repository_id=None,
                configured_plan=None,
                configured_guidance_paths=None,
                configured_probe_query="query",
                configured_expected_paths=None,
                configured_probe_timeout_seconds=30,
            )
        )

    tracked.write_text("clean\n", encoding="utf-8")
    monkeypatch.setattr(agent_evaluation, "get_repository_preflight", stale_preflight)
    with pytest.raises(EvaluationInfrastructureError, match="indexed commit"):
        asyncio.run(
            _prepare_agent_context(
                suite,
                repository_root=target,
                repository_id=None,
                configured_plan=None,
                configured_guidance_paths=None,
                configured_probe_query="query",
                configured_expected_paths=None,
                configured_probe_timeout_seconds=30,
            )
        )


def test_configured_integration_requires_exact_plan_binding_and_probes(
    monkeypatch: Any, tmp_path: Path
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "AGENTS.md").write_text("# Configured guidance\n", encoding="utf-8")
    (target / ".gitignore").write_text("/AGENTS.override.md\n", encoding="utf-8")
    (target / "AGENTS.override.md").write_text(
        "# Installed CodeMesh guidance\n", encoding="utf-8"
    )
    (target / ".codex").mkdir()
    (target / ".codex" / "config.toml").write_text(
        "\n".join(
            [
                "[mcp_servers.graphify]",
                'command = "graphify"',
                'args = ["mcp"]',
                f'cwd = "{target.as_posix()}"',
                "required = true",
                'enabled_tools = ["graphify_search"]',
                'env_vars = ["GRAPHIFY_URL"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    _git(target, "init", "--quiet")
    _git(target, "config", "user.name", "CodeMesh Test")
    _git(target, "config", "user.email", "codemesh@example.invalid")
    _git(target, "add", "AGENTS.md", ".gitignore")
    _git(target, "commit", "--quiet", "-m", "fixture")
    base_commit = _git(target, "rev-parse", "HEAD").strip()
    codemesh_root = Path(__file__).resolve().parents[2]
    binding = RepositoryBinding(
        "project:test",
        "checkout:test",
        str(target),
        "view:test",
    )
    plan = create_installation_plan(
        target,
        codemesh_root,
        binding,
        include_onboarding=False,
    )
    apply_installation_plan(plan, plan.plan_hash)
    preflight = {
        "repository_id": "project:test",
        "repository": {
            "project_id": "project:test",
            "checkout_id": "checkout:test",
            "root_path": str(target),
            "source_view_hash": "view:test",
        },
    }

    async def fake_positive(received_plan: Any, **kwargs: Any) -> dict[str, Any]:
        assert received_plan == plan
        assert kwargs["query"] == "configured query"
        assert kwargs["expected_paths"] == ["src/A.cs"]
        return {
            "schema_version": "codemesh-runtime-probe-v1",
            "passed": True,
            "provider_mode": "none",
            "profile": "normal",
            "server_name": "codemesh",
            "project_id": "project:test",
            "checkout_id": "checkout:test",
            "repository_root": str(target),
            "snapshot_id": "snapshot:test",
            "source_view_hash": "view:test",
            "indexed_commit": base_commit,
            "current_commit": base_commit,
            "freshness_status": "fresh",
            "binding_status": "accepted",
            "tools": plan.launch["expected_tools"],
            "context_query": "configured query",
            "context_item_count": 1,
            "returned_paths": ["src/A.cs"],
            "expected_paths": ["src/A.cs"],
            "duration_ms": 1.5,
        }

    async def fake_negative(received_plan: Any, **kwargs: Any) -> dict[str, Any]:
        assert received_plan == plan
        assert kwargs["checkout_id"].endswith(":codemesh-eval-rejection")
        assert kwargs["expected_substrings"] == ["bound_repository_missing"]
        return {
            "schema_version": "codemesh-runtime-rejection-probe-v1",
            "passed": True,
            "rejected": True,
            "provider_mode": "none",
            "profile": "normal",
            "checkout_id": kwargs["checkout_id"],
            "expected_substrings": ["bound_repository_missing"],
            "diagnostic": "binding rejected: bound_repository_missing",
            "duration_ms": 1.0,
        }

    monkeypatch.setattr(agent_evaluation, "run_runtime_probe", fake_positive)
    monkeypatch.setattr(agent_evaluation, "run_runtime_rejection_probe", fake_negative)

    metadata, control_overrides, treatment_overrides, guidance_files = asyncio.run(
        _prepare_configured_integration(
            plan,
            root=target,
            base_commit=base_commit,
            codemesh_root=codemesh_root,
            preflight=preflight,
            guidance_paths=["AGENTS.override.md"],
            probe_query="configured query",
            expected_paths=["src/A.cs"],
            timeout_seconds=30,
            baseline_mcp_servers=["graphify"],
        )
    )

    assert metadata["plan_hash"] == plan.plan_hash
    assert metadata["profile"] == "normal"
    assert metadata["guidance"][0]["path"] == "AGENTS.override.md"
    assert len(metadata["guidance"][0]["sha256"]) == 64
    assert metadata["guidance"][0]["source"] == "installed-ignored"
    assert guidance_files[0].content == b"# Installed CodeMesh guidance\n"
    assert len(metadata["positive_probe"]["report_sha256"]) == 64
    assert "diagnostic" not in metadata["rejection_probe"]
    assert metadata["baseline_mcp_servers"][0]["name"] == "graphify"
    assert any("mcp_servers.graphify.command" in value for value in control_overrides)
    assert not any("mcp_servers.codemesh" in value for value in control_overrides)
    assert treatment_overrides[: len(control_overrides)] == control_overrides
    assert any('"--profile", "normal"' in value for value in treatment_overrides)
    assert any("default_tools_approval_mode" in value for value in treatment_overrides)

    mismatched = json.loads(json.dumps(preflight))
    mismatched["repository"]["checkout_id"] = "checkout:other"
    with pytest.raises(EvaluationInfrastructureError, match="checkout"):
        asyncio.run(
            _prepare_configured_integration(
                plan,
                root=target,
                base_commit=base_commit,
                codemesh_root=codemesh_root,
                preflight=mismatched,
                guidance_paths=["AGENTS.md"],
                probe_query="configured query",
                expected_paths=["src/A.cs"],
                timeout_seconds=30,
                baseline_mcp_servers=["graphify"],
            )
        )

    (target / ".codex" / "config.toml").write_text(
        "# changed after review\n", encoding="utf-8"
    )
    with pytest.raises(EvaluationInfrastructureError, match="not applied unchanged"):
        asyncio.run(
            _prepare_configured_integration(
                plan,
                root=target,
                base_commit=base_commit,
                codemesh_root=codemesh_root,
                preflight=preflight,
                guidance_paths=["AGENTS.md"],
                probe_query="configured query",
                expected_paths=["src/A.cs"],
                timeout_seconds=30,
                baseline_mcp_servers=["graphify"],
            )
        )


def test_configured_agent_report_retains_identity_and_prompt_parity(
    monkeypatch: Any, tmp_path: Path
) -> None:
    repository = tmp_path / "repository"
    (repository / "src").mkdir(parents=True)
    (repository / "src" / "A.cs").write_text("class A {}\n", encoding="utf-8")
    _git(repository, "init", "--quiet")
    _git(repository, "config", "user.name", "CodeMesh Test")
    _git(repository, "config", "user.email", "codemesh@example.invalid")
    _git(repository, "add", "src/A.cs")
    _git(repository, "commit", "--quiet", "-m", "fixture")
    base_commit = _git(repository, "rev-parse", "HEAD").strip()
    suite = AgentSuite(
        name="configured",
        repository_commit=base_commit,
        integration_mode="configured",
        tasks=[
            AgentTask(
                id="answer",
                description="answer",
                task_type="answer",
                prompt="Explain A.",
                targets=[RetrievalTarget(file_path="src/A.cs")],
            )
        ],
    )
    configured_identity = {
        "schema_version": "codemesh-configured-agent-integration-v1",
        "plan_hash": "plan:test",
        "profile": "normal",
    }
    context = AgentEvaluationContext(
        root=repository,
        base_commit=base_commit,
        preflight={"repository_id": "project:test"},
        freshness={"current_branch": "main"},
        mcp_cwd=tmp_path,
        codemesh_root=tmp_path,
        codemesh_source_commit="codemesh:test",
        codemesh_source_branch="main",
        integration_mode="configured",
        control_mcp_config=(
            "mcp_servers={}",
            'mcp_servers.graphify.command="graphify"',
        ),
        treatment_mcp_config=('mcp_servers.codemesh.command="uv"',),
        configured_integration=configured_identity,
        configured_guidance_files=(
            ConfiguredGuidanceFile(
                path="AGENTS.override.md",
                content=b"# Installed CodeMesh guidance\n",
                sha256=hashlib.sha256(b"# Installed CodeMesh guidance\n").hexdigest(),
            ),
        ),
    )

    async def fake_context(*_args: Any, **_kwargs: Any) -> AgentEvaluationContext:
        return context

    requests: list[AgentRunRequest] = []
    observed_guidance: list[str] = []

    class FakeRunner:
        async def run(self, request: AgentRunRequest) -> AgentRunResult:
            requests.append(request)
            observed_guidance.append(
                (request.cwd / "AGENTS.override.md").read_text(encoding="utf-8")
            )
            return AgentRunResult(
                completed=True,
                exit_code=0,
                duration_ms=10,
                final_message=json.dumps(
                    {
                        "answer": "A is implemented here.",
                        "citations": [
                            {
                                "file_path": "src/A.cs",
                                "start_line": 1,
                                "end_line": 1,
                                "stable_key": None,
                            }
                        ],
                    }
                ),
                usage={"input_tokens": 5, "output_tokens": 2},
                mcp_calls=(
                    ["codemesh.codemesh_get_context_package"]
                    if request.condition == "treatment"
                    else []
                ),
            )

    monkeypatch.setattr(agent_evaluation, "_prepare_agent_context", fake_context)
    report = asyncio.run(
        run_agent_evaluation(
            suite,
            tmp_path / "suite.json",
            model="test-model",
            repetitions=1,
            output_dir=tmp_path / "artifacts",
            runner=FakeRunner(),
        )
    )

    assert report.metadata["adoption_mode"] == "configured"
    assert report.metadata["integration_mode"] == "configured"
    assert report.metadata["prompt_parity"] is True
    assert report.metadata["treatment_guidance"] is None
    assert report.metadata["configured_integration"] == configured_identity
    assert len(requests) == 2
    assert {request.prompt for request in requests} == {"Explain A."}
    assert observed_guidance == [
        "# Installed CodeMesh guidance\n",
        "# Installed CodeMesh guidance\n",
    ]
    control = next(request for request in requests if request.condition == "control")
    treatment = next(
        request for request in requests if request.condition == "treatment"
    )
    assert control.mcp_config == context.control_mcp_config
    assert treatment.mcp_config == context.treatment_mcp_config


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
    assert client.parameters.args[-2:] == ["--profile", "diagnostic"]
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


def test_repository_preflight_stale_diagnostic_retains_candidate_identity(
    monkeypatch: Any,
) -> None:
    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        def connect(self) -> "FakeClient":
            return self

        async def call(
            self, _tool: str, _arguments: dict[str, Any]
        ) -> tuple[dict[str, Any], float]:
            return (
                {
                    "data": {
                        "freshness": {
                            "status": "stale",
                            "detail": "Candidate identity does not match.",
                            "indexed_commit": "indexed:test",
                            "current_commit": "current:test",
                            "working_tree_dirty": False,
                            "indexed_source_view_hash": "view:test",
                        }
                    }
                },
                1.0,
            )

    monkeypatch.setattr(
        "codemesh_agent_access.evaluation.live.McpEvaluationClient",
        lambda **_kwargs: FakeClient(),
    )

    with pytest.raises(EvaluationInfrastructureError) as captured:
        asyncio.run(get_repository_preflight("project:test"))

    diagnostic = str(captured.value)
    assert "indexed_commit='indexed:test'" in diagnostic
    assert "current_commit='current:test'" in diagnostic
    assert "working_tree_dirty=False" in diagnostic
    assert "indexed_source_view_hash='view:test'" in diagnostic


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


def test_live_tool_source_identity_reports_commit_and_dirtiness(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "tracked.txt").write_text("clean\n", encoding="utf-8")
    _git(source, "init", "--quiet")
    _git(source, "config", "user.name", "CodeMesh Test")
    _git(source, "config", "user.email", "codemesh@example.invalid")
    _git(source, "add", "tracked.txt")
    _git(source, "commit", "--quiet", "-m", "fixture")

    clean = get_tool_source_identity(source)
    assert clean["available"] is True
    assert clean["commit"] == _git(source, "rev-parse", "HEAD").strip()
    assert clean["working_tree_dirty"] is False

    (source / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    assert get_tool_source_identity(source)["working_tree_dirty"] is True


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


def test_answer_grading_preserves_hidden_and_absolute_paths(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "main.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: main\n", encoding="utf-8")
    target = RetrievalTarget(file_path=".github/workflows/main.yml")

    for file_path in [".github/workflows/main.yml", str(workflow.resolve())]:
        answer = json.dumps(
            {
                "answer": "validation",
                "citations": [
                    {
                        "file_path": file_path,
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
            }
        )

        assert _grade_answer(answer, [target], tmp_path) == []


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
    assert 'mcp_servers.codemesh.default_tools_approval_mode="approve"' in treatment
    assert any(
        '"--profile", "diagnostic"' in value
        for value in treatment
        if value.startswith("mcp_servers.codemesh.args=")
    )
    assert any(
        value.startswith("mcp_servers.codemesh.enabled_tools=") for value in treatment
    )
    assert not any("codemesh_delete_repository" in value for value in treatment)
    assert control[:3] == ["--ask-for-approval", "never", "exec"]
    assert treatment[:3] == ["--ask-for-approval", "never", "exec"]
    assert "--ephemeral" in treatment
    assert "--ignore-user-config" in treatment

    legacy = runner._arguments(
        AgentRunRequest(condition="treatment", **common),
        supports_ignore_user_config=False,
    )
    assert "--ignore-user-config" not in legacy
    assert "--ask-for-approval" in legacy

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
    assert summary["codemesh_attributable_wins"] == 3
    assert summary["codemesh_adoption_rate"] == 1
    assert summary["codemesh_adopted_pair_count"] == 3

    runs[-1].safety_violation = True
    verdict, _summary = classify_agent_results(runs, suite)
    assert verdict == "regressed"


def test_agent_classifier_does_not_credit_unadopted_efficiency() -> None:
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
                    passed=True,
                    duration_ms=100,
                    input_tokens=100,
                ),
                AgentExecutionReport(
                    task_id="answer",
                    repetition=repetition,
                    condition="treatment",
                    completed=True,
                    passed=True,
                    duration_ms=50,
                    input_tokens=50,
                ),
            ]
        )

    verdict, summary = classify_agent_results(runs, suite)

    assert verdict == "neutral"
    assert summary["codemesh_adoption_rate"] == 0
    assert summary["codemesh_adopted_pair_count"] == 0
    assert summary["codemesh_efficiency_pair_count"] == 0
    assert summary["duration_delta"] == -0.5
    assert summary["token_delta"] == -0.5
    assert summary["codemesh_duration_delta"] == 0
    assert summary["codemesh_token_delta"] == 0


def test_assisted_treatment_guidance_does_not_change_control_prompt() -> None:
    guidance = "Start with the indexed context package, then verify source."

    assert _condition_prompt("task", "control", guidance) == "task"
    assert _condition_prompt("task", "treatment", guidance) == (
        "Start with the indexed context package, then verify source.\n\ntask"
    )


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
