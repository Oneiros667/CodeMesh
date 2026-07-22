from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from codemesh_agent_access.evaluation.benchmark import (
    _build_review_packet,
    _difficulty_pass_counts,
    _efficiency_band,
    _grade_query_run,
    _scenario_results,
    _tool_score,
    _weighted_score,
    compare_model_reports,
    finalize_model_report,
    run_model_benchmark,
)
from codemesh_agent_access.evaluation import benchmark
from codemesh_agent_access.evaluation.benchmark_mcp import BenchmarkCallGuard
from codemesh_agent_access.evaluation.codex import AgentRunResult
from codemesh_agent_access.evaluation.models import (
    BenchmarkRunReport,
    CriterionWeights,
    ModelBenchmarkReport,
    ModelBenchmarkSuite,
    ReviewFile,
    ToolPolicy,
    load_suite,
)


def test_model_suite_has_complete_matrices_and_weights() -> None:
    suite, _path = load_suite("codemesh-model", "model-benchmark")

    assert sum(suite.weights.model_dump().values()) == 100
    assert {item.family_id for item in suite.questions} == {
        "registry-persistence",
        "repository-cleanup",
        "refresh-self",
        "agent-access-contracts",
        "csharp-parsing",
        "deployment-parsing",
        "freshness-safety",
        "impact-validation",
    }
    assert all(item.expected_facts for item in suite.questions)
    assert all(item.expected_facts for item in suite.change_scenarios)

    incomplete = suite.model_dump()
    incomplete["questions"].pop()
    with pytest.raises(ValidationError):
        ModelBenchmarkSuite.model_validate(incomplete)
    with pytest.raises(ValidationError):
        CriterionWeights(speed=4)


def test_tool_guard_blocks_excess_calls_without_recording_values(
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "audit.json"
    guard = BenchmarkCallGuard(
        {
            "allowed_tools": ["codemesh_search_context"],
            "max_calls": 1,
            "per_tool_limits": {"codemesh_search_context": 1},
        },
        audit_path,
    )

    guard("codemesh_search_context", {"query": "sensitive value", "limit": 2})
    with pytest.raises(RuntimeError, match="budget exceeded"):
        guard("codemesh_search_context", {"query": "do-not-record"})

    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert payload["attempts"][1]["blocked"] is True
    assert payload["attempts"][0]["argument_names"] == ["limit", "query"]
    assert "sensitive value" not in audit_path.read_text(encoding="utf-8")
    assert "do-not-record" not in audit_path.read_text(encoding="utf-8")


def test_tool_policy_scoring_checks_sequence_and_budget() -> None:
    policy = ToolPolicy(
        allowed_tools=["status", "search"],
        max_calls=2,
        required_sequence=["status", "search"],
    )
    score, failures = _tool_score(
        policy,
        {"attempts": [{"tool": "search", "blocked": False}]},
    )

    assert score == 2
    assert any("sequence" in failure for failure in failures)


def test_query_report_flags_and_scrubs_canary_leakage(tmp_path: Path) -> None:
    suite, _suite_path = load_suite("codemesh-model", "model-benchmark")
    question = next(
        item for item in suite.questions if item.id == "freshness-safety-hard"
    )
    target = tmp_path / question.targets[0].file_path
    target.parent.mkdir(parents=True)
    target.write_text("line one\nline two\n", encoding="utf-8")
    _git(tmp_path, "init", "--quiet")
    _git(tmp_path, "config", "user.name", "CodeMesh Test")
    _git(tmp_path, "config", "user.email", "codemesh@example.invalid")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "--quiet", "-m", "fixture")
    canary = question.forbidden_substrings[0]
    result = AgentRunResult(
        completed=True,
        exit_code=0,
        duration_ms=10,
        usage={"input_tokens": 10, "output_tokens": 2},
        mcp_call_attempts=[
            "codemesh.codemesh_search_context",
            "benchmark_response.submit_benchmark_answer",
        ],
    )
    payload = {
        "answer": f"Leaked {canary}",
        "facts": question.expected_facts,
        "citations": [
            {
                "file_path": question.targets[0].file_path,
                "start_line": 1,
                "end_line": 2,
            }
        ],
    }

    report = _grade_query_run(
        question,
        1,
        tmp_path,
        result,
        {"attempts": [{"tool": "codemesh_search_context", "blocked": False}]},
        payload,
        suite.weights,
    )

    assert report.safety_violation is True
    assert report.passed is False
    assert canary not in report.answer


def test_weighted_scoring_efficiency_bands_and_repeat_aggregation() -> None:
    weights = CriterionWeights()
    scores = {name: 4.0 for name in weights.model_dump()}
    assert _weighted_score(scores, weights) == 100
    assert [_efficiency_band(value, 100) for value in (100, 125, 150, 200, 201)] == [
        4,
        3,
        2,
        1,
        0,
    ]

    runs = [
        _run("arbitrary-one", "easy", 1, True),
        _run("arbitrary-one", "easy", 2, True),
        _run("arbitrary-one", "easy", 3, False),
        _run("another-id", "hard", 1, True),
        _run("another-id", "hard", 2, False),
        _run("another-id", "hard", 3, False),
    ]
    results = _scenario_results(runs)
    assert results == {"arbitrary-one": True, "another-id": False}
    assert _difficulty_pass_counts(runs, results) == {
        "easy": 1,
        "medium": 0,
        "hard": 0,
    }


def test_review_finalization_and_cohort_comparison(tmp_path: Path) -> None:
    _suite, suite_path = load_suite("codemesh-model", "model-benchmark")
    first_path = tmp_path / "first.json"
    review_path = tmp_path / "reviews.json"
    reviewed_path = tmp_path / "first-reviewed.json"
    first = _report("model-a", suite_path, duration=100, tokens=100)
    first.metadata["review_map"] = {
        "anonymous": {
            "scenario_id": "query-one",
            "repetition": 1,
            "dual_review": False,
        }
    }
    first_path.write_text(first.model_dump_json(indent=2), encoding="utf-8")
    review_path.write_text(
        ReviewFile(
            reviews=[
                {
                    "anonymous_id": "anonymous",
                    "score": 4,
                    "reviewer_id": "reviewer-one",
                }
            ]
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )

    reviewed = finalize_model_report(first_path, review_path, output_path=reviewed_path)
    assert reviewed.status == "reviewed"
    assert reviewed.runs[0].criterion_scores["insight"] == 4

    second = _report("model-b", suite_path, duration=200, tokens=200)
    second.status = "reviewed"
    second_path = tmp_path / "second-reviewed.json"
    second_path.write_text(second.model_dump_json(indent=2), encoding="utf-8")
    comparison = compare_model_reports([reviewed_path, second_path])

    assert comparison.comparable is True
    assert {item["model"] for item in comparison.rankings} == {"model-a", "model-b"}


def test_review_packet_blinds_ids_and_dual_reviews_ten_percent() -> None:
    suite, _suite_path = load_suite("codemesh-model", "model-benchmark")
    runs = []
    for question in suite.questions:
        run = _run(question.id, question.difficulty, 1, True)
        run.answer = "Grounded answer"
        runs.append(run)

    packet, review_map = _build_review_packet(runs, suite, seed=137)

    assert len(packet["items"]) == 24
    assert sum(item["requires_second_reviewer"] for item in packet["items"]) == 3
    assert all("scenario_id" not in item for item in packet["items"])
    assert set(review_map) == {item["anonymous_id"] for item in packet["items"]}


def test_comparison_marks_different_benchmark_settings_non_comparable(
    tmp_path: Path,
) -> None:
    _suite, suite_path = load_suite("codemesh-model", "model-benchmark")
    first = _report("one", suite_path, duration=100, tokens=100)
    second = _report("two", suite_path, duration=100, tokens=100)
    first.status = "reviewed"
    second.status = "reviewed"
    second.metadata["temperature"] = 0.7
    paths = [tmp_path / "one.json", tmp_path / "two.json"]
    paths[0].write_text(first.model_dump_json(), encoding="utf-8")
    paths[1].write_text(second.model_dump_json(), encoding="utf-8")

    comparison = compare_model_reports(paths)

    assert comparison.comparable is False
    assert any("temperature" in failure for failure in comparison.failures)


def test_full_benchmark_orchestration_is_deterministic_and_keeps_source_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repository, "init", "--quiet")
    _git(repository, "config", "user.name", "CodeMesh Test")
    _git(repository, "config", "user.email", "codemesh@example.invalid")
    _git(repository, "add", "README.md")
    _git(repository, "commit", "--quiet", "-m", "fixture")
    commit = _git(repository, "rev-parse", "HEAD").strip()
    suite, suite_path = load_suite("codemesh-model", "model-benchmark")
    live_calls = []

    async def fake_preflight(_repository_id: str) -> dict[str, object]:
        return {
            "repository_id": "code_mesh",
            "freshness": {"indexed_commit": commit, "current_commit": commit},
        }

    async def fake_live(*_args: object, **_kwargs: object) -> object:
        live_calls.append(True)
        return SimpleNamespace(
            passed=True,
            suite="codemesh-live",
            summary={"recall_at_k": 1.0},
        )

    async def fake_query(question: object, **kwargs: object) -> BenchmarkRunReport:
        return _run(
            question.id,
            question.difficulty,
            int(kwargs["repetition"]),
            True,
        )

    async def fake_change(
        _suite_path: Path, scenario: object, **kwargs: object
    ) -> BenchmarkRunReport:
        run = _run(
            scenario.id,
            scenario.difficulty,
            int(kwargs["repetition"]),
            True,
        )
        run.tier = "change"
        run.condition = str(kwargs["condition"])
        run.validation = [{"passed": True}]
        return run

    monkeypatch.setattr(benchmark, "get_repository_preflight", fake_preflight)
    monkeypatch.setattr(benchmark, "run_live_evaluation", fake_live)
    monkeypatch.setattr(benchmark, "_run_query", fake_query)
    monkeypatch.setattr(benchmark, "_run_change", fake_change)

    report = asyncio.run(
        run_model_benchmark(
            suite,
            suite_path,
            model="fixture-model",
            tier="all",
            repository_root=repository,
            output_dir=tmp_path / "artifacts",
        )
    )

    assert len(report.runs) == 126
    assert sum(run.tier == "query" for run in report.runs) == 72
    assert sum(run.tier == "change" for run in report.runs) == 54
    assert live_calls == [True]
    assert _git(repository, "status", "--porcelain") == ""
    assert (tmp_path / "artifacts" / "report.json").is_file()
    assert (tmp_path / "artifacts" / "review-packet.json").is_file()


def _run(
    scenario_id: str,
    difficulty: str,
    repetition: int,
    passed: bool,
    *,
    duration: float = 100,
    tokens: int = 100,
) -> BenchmarkRunReport:
    return BenchmarkRunReport(
        scenario_id=scenario_id,
        family_id="family",
        difficulty=difficulty,
        tier="query",
        repetition=repetition,
        condition="treatment",
        completed=True,
        passed=passed,
        duration_ms=duration,
        input_tokens=tokens,
        criterion_scores={
            "accuracy": 4.0 if passed else 0.0,
            "instruction_following": 4.0 if passed else 0.0,
            "tool_use": 4.0,
            "safety": 4.0,
            "insight": 2.0 if passed else 0.0,
            "reliability": 4.0 if passed else 0.0,
            "token_efficiency": 2.0 if passed else 0.0,
            "speed": 2.0 if passed else 0.0,
        },
        weighted_score=85.0 if passed else 25.0,
    )


def _report(
    model: str, suite_path: Path, *, duration: float, tokens: int
) -> ModelBenchmarkReport:
    return ModelBenchmarkReport(
        suite="codemesh-model",
        model=model,
        tier="query",
        seed=137,
        repetitions=3,
        generated_at="2026-01-01T00:00:00Z",
        metadata={
            "suite_path": str(suite_path),
            "base_commit": "commit",
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 20,
            "context_length": 262144,
            "chat_template_hash": "template",
            "hardware": "host",
            "weights": CriterionWeights().model_dump(),
        },
        runs=[_run("query-one", "easy", 1, True, duration=duration, tokens=tokens)],
    )


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout
