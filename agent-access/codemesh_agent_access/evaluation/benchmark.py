from __future__ import annotations

import hashlib
import json
import math
import platform
import random
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any, Literal

from .agent import (
    _changed_paths,
    _git,
    _git_root,
    _grade_answer,
    _run_task_condition,
)
from .codex import AgentRunRequest, AgentRunner, CodexRunner, sanitize_text
from .live import (
    EvaluationInfrastructureError,
    get_repository_preflight,
    run_live_evaluation,
)
from .models import (
    AgentTask,
    BenchmarkChangeScenario,
    BenchmarkCitation,
    BenchmarkQuestion,
    BenchmarkRunReport,
    CriterionWeights,
    InsightReview,
    ModelBenchmarkReport,
    ModelBenchmarkSuite,
    ModelComparisonReport,
    ReviewFile,
    ToolPolicy,
    load_suite,
    validate_suite_artifacts,
)
from .paths import managed_artifact_path, validate_artifact_id


_CRITERIA = (
    "accuracy",
    "instruction_following",
    "tool_use",
    "safety",
    "insight",
    "reliability",
    "token_efficiency",
    "speed",
)


async def run_model_benchmark(
    suite: ModelBenchmarkSuite,
    suite_path: Path,
    *,
    model: str,
    tier: Literal["query", "change", "all"] = "query",
    local_provider: Literal["lmstudio", "ollama"] | None = None,
    codex_executable: str = "codex",
    reasoning_effort: str = "medium",
    repetitions: int = 3,
    seed: int = 137,
    repository_root: str | Path | None = None,
    repository_id: str | None = None,
    output_dir: str | Path | None = None,
    keep_raw_traces: bool = False,
    keep_workspaces: bool = False,
    runner: AgentRunner | None = None,
    verify_live: bool = True,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    context_length: int | None = None,
    chat_template_hash: str | None = None,
    quantization: str | None = None,
    hardware: str | None = None,
    provider: str | None = None,
) -> ModelBenchmarkReport:
    if repetitions < suite.thresholds.minimum_repetitions:
        raise ValueError(
            f"Model benchmark requires at least {suite.thresholds.minimum_repetitions} repetitions."
        )
    started = perf_counter()
    validate_suite_artifacts(suite, suite_path)
    root = _git_root(Path(repository_root) if repository_root else Path.cwd())
    if _git(root, "status", "--porcelain"):
        raise EvaluationInfrastructureError(
            "Model benchmark requires a clean source checkout."
        )
    base_commit = _git(root, "rev-parse", "HEAD").strip()
    resolved_repository = repository_id or suite.repository_id
    preflight = await get_repository_preflight(resolved_repository)
    freshness = preflight.get("freshness") or {}
    if (
        freshness.get("indexed_commit") != base_commit
        or freshness.get("current_commit") != base_commit
    ):
        raise EvaluationInfrastructureError(
            "The indexed commit, current checkout, and benchmark base commit must match."
        )

    live_summary: dict[str, Any] = {"verified": False}
    if verify_live:
        live_suite, _ = load_suite("codemesh-live", "live")
        live_report = await run_live_evaluation(
            live_suite,
            repository_id=resolved_repository,
            repetitions=3,
            warmup=1,
            allow_stale=False,
            keep_raw_traces=False,
        )
        live_summary = {
            "verified": True,
            "passed": live_report.passed,
            "suite": live_report.suite,
            "summary": live_report.summary,
        }
        if not live_report.passed:
            raise EvaluationInfrastructureError(
                "The live CodeMesh retrieval suite must pass before model scoring."
            )

    destination = (
        Path(output_dir)
        if output_dir
        else root / ".codemesh-evals" / _run_name(suite.name, model)
    )
    destination.mkdir(parents=True, exist_ok=False)
    benchmark_runner = runner or CodexRunner(codex_executable)
    mcp_cwd = Path(__file__).resolve().parents[2]
    rng = random.Random(seed)
    runs: list[BenchmarkRunReport] = []

    if tier in {"query", "all"}:
        for question in suite.questions:
            for repetition in range(1, repetitions + 1):
                runs.append(
                    await _run_query(
                        question,
                        repetition=repetition,
                        root=root,
                        base_commit=base_commit,
                        model=model,
                        local_provider=local_provider,
                        reasoning_effort=reasoning_effort,
                        runner=benchmark_runner,
                        mcp_cwd=mcp_cwd,
                        artifact_dir=destination,
                        keep_raw_traces=keep_raw_traces,
                        keep_workspace=keep_workspaces,
                        weights=suite.weights,
                    )
                )

    if tier in {"change", "all"}:
        for scenario in suite.change_scenarios:
            for repetition in range(1, repetitions + 1):
                conditions = ["control", "treatment"]
                if rng.random() < 0.5:
                    conditions.reverse()
                for condition in conditions:
                    runs.append(
                        await _run_change(
                            suite_path,
                            scenario,
                            repetition=repetition,
                            condition=condition,
                            root=root,
                            base_commit=base_commit,
                            model=model,
                            local_provider=local_provider,
                            reasoning_effort=reasoning_effort,
                            runner=benchmark_runner,
                            mcp_cwd=mcp_cwd,
                            artifact_dir=destination,
                            keep_raw_traces=keep_raw_traces,
                            keep_workspaces=keep_workspaces,
                            weights=suite.weights,
                        )
                    )

    _apply_reliability_and_provisional_efficiency(runs, suite.weights, repetitions)
    summary = _summarize(runs, suite)
    review_packet, review_map = _build_review_packet(runs, suite, seed)
    (destination / "review-packet.json").write_text(
        json.dumps(review_packet, indent=2), encoding="utf-8"
    )
    report = ModelBenchmarkReport(
        suite=suite.name,
        model=model,
        tier=tier,
        seed=seed,
        repetitions=repetitions,
        generated_at=datetime.now(timezone.utc).isoformat(),
        qualified=bool(summary.get("query_qualified")),
        certified=bool(summary.get("change_certified")),
        query_score=summary.get("query_score"),
        change_score=summary.get("change_score"),
        final_score=summary.get("final_score"),
        metadata={
            "repository_id": preflight.get("repository_id") or resolved_repository,
            "base_commit": base_commit,
            "model_provider": provider or local_provider or "default",
            "quantization": quantization,
            "codex_executable": codex_executable,
            "reasoning_effort": reasoning_effort,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "context_length": context_length,
            "chat_template_hash": chat_template_hash,
            "hardware": hardware or platform.platform(),
            "weights": suite.weights.model_dump(),
            "live_preflight": live_summary,
            "review_map": review_map,
            "raw_traces_retained": keep_raw_traces,
            "source_checkout_modified": False,
            "artifact_directory": str(destination.resolve()),
            "suite_path": str(suite_path.resolve()),
            "duration_ms": round((perf_counter() - started) * 1000, 3),
        },
        summary=summary,
        runs=runs,
    )
    _write_report(destination / "report.json", report)
    return report


async def _run_query(
    question: BenchmarkQuestion,
    *,
    repetition: int,
    root: Path,
    base_commit: str,
    model: str,
    local_provider: Literal["lmstudio", "ollama"] | None,
    reasoning_effort: str,
    runner: AgentRunner,
    mcp_cwd: Path,
    artifact_dir: Path,
    keep_raw_traces: bool,
    keep_workspace: bool,
    weights: CriterionWeights,
) -> BenchmarkRunReport:
    validate_artifact_id(question.id)
    run_dir = managed_artifact_path(
        artifact_dir, f"{question.id}-{repetition}-treatment"
    )
    retained = managed_artifact_path(
        artifact_dir, "workspaces", f"{question.id}-{repetition}"
    )
    temp_parent = Path(tempfile.mkdtemp(prefix="codemesh-model-query-"))
    workspace = temp_parent / "workspace"
    response_path = temp_parent / "response.json"
    audit_path = temp_parent / "tool-audit.json"
    try:
        _clone_at_commit(root, workspace, base_commit)
        prompt = _query_prompt(question)
        result = await runner.run(
            AgentRunRequest(
                prompt=prompt,
                cwd=workspace,
                condition="treatment",
                model=model,
                local_provider=local_provider,
                reasoning_effort=reasoning_effort,
                sandbox="read-only",
                timeout_seconds=question.timeout_seconds,
                mcp_cwd=mcp_cwd,
                keep_raw_traces=True,
                mcp_config=tuple(
                    _benchmark_mcp_config(
                        mcp_cwd, question.tool_policy, audit_path, response_path
                    )
                ),
            )
        )
        audit = _load_json(audit_path, {"attempts": []})
        payload = _load_json(response_path, {})
        report = _grade_query_run(
            question,
            repetition,
            workspace,
            result,
            audit,
            payload,
            weights,
        )
        if not keep_raw_traces:
            report.raw_events = None
        if keep_raw_traces:
            run_dir.mkdir(parents=True, exist_ok=False)
            (run_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(event) for event in result.raw_events),
                encoding="utf-8",
            )
            (run_dir / "response.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        if keep_workspace:
            retained.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(workspace), retained)
        return report
    finally:
        shutil.rmtree(temp_parent, ignore_errors=True)


async def _run_change(
    suite_path: Path,
    scenario: BenchmarkChangeScenario,
    *,
    repetition: int,
    condition: str,
    root: Path,
    base_commit: str,
    model: str,
    local_provider: Literal["lmstudio", "ollama"] | None,
    reasoning_effort: str,
    runner: AgentRunner,
    mcp_cwd: Path,
    artifact_dir: Path,
    keep_raw_traces: bool,
    keep_workspaces: bool,
    weights: CriterionWeights,
) -> BenchmarkRunReport:
    validate_artifact_id(scenario.id)
    audit_path = managed_artifact_path(
        artifact_dir, ".runtime", f"{scenario.id}-{repetition}-{condition}.json"
    )
    policy = scenario.tool_policy
    mcp_config = (
        tuple(_proxy_only_mcp_config(mcp_cwd, policy, audit_path))
        if condition == "treatment"
        else ("mcp_servers={}",)
    )
    task = AgentTask(
        id=scenario.id,
        description=scenario.description,
        task_type="change",
        prompt=scenario.prompt,
        setup_patch=scenario.setup_patch,
        validation=scenario.validation,
        required_changed_paths=scenario.required_changed_paths,
        allowed_changed_paths=scenario.allowed_changed_paths,
        forbidden_changed_paths=scenario.forbidden_changed_paths,
        command_policy=scenario.command_policy,
        timeout_seconds=scenario.timeout_seconds,
    )
    agent_report = await _run_task_condition(
        suite_path=suite_path,
        task=task,
        repetition=repetition,
        condition=condition,
        root=root,
        base_commit=base_commit,
        model=model,
        local_provider=local_provider,
        reasoning_effort=reasoning_effort,
        mcp_cwd=mcp_cwd,
        keep_raw_traces=keep_raw_traces,
        keep_workspaces=keep_workspaces,
        runner=runner,
        artifact_dir=artifact_dir,
        mcp_config=mcp_config,
    )
    audit = _load_json(audit_path, {"attempts": []})
    blocked = [
        str(item.get("tool"))
        for item in audit.get("attempts", [])
        if item.get("blocked")
    ]
    tool_score, tool_failures = _tool_score(
        policy,
        audit,
        condition=condition,
        failed_calls=agent_report.mcp_failed_calls,
    )
    failures = list(agent_report.failures) + tool_failures
    validation_passes = sum(
        item.get("passed") is True for item in agent_report.validation
    )
    validation_count = len(agent_report.validation)
    accuracy = (
        4.0 * validation_passes / validation_count
        if validation_count
        else 4.0
        if agent_report.passed
        else 0.0
    )
    scores: dict[str, float | None] = {
        "accuracy": round(accuracy, 3),
        "instruction_following": 4.0
        if agent_report.completed and not agent_report.failures and not blocked
        else 2.0
        if agent_report.completed
        else 0.0,
        "tool_use": tool_score,
        "safety": 0.0 if agent_report.safety_violation else 4.0,
        "insight": None if agent_report.passed else 0.0,
        "reliability": None,
        "token_efficiency": None,
        "speed": None,
    }
    passed = (
        agent_report.passed
        and scores["accuracy"] >= 3
        and scores["instruction_following"] >= 3
        and scores["safety"] == 4
    )
    return BenchmarkRunReport(
        scenario_id=scenario.id,
        family_id=scenario.family_id,
        difficulty=scenario.difficulty,
        tier="change",
        repetition=repetition,
        condition=condition,  # type: ignore[arg-type]
        completed=agent_report.completed,
        passed=passed,
        safety_violation=agent_report.safety_violation,
        duration_ms=agent_report.duration_ms,
        input_tokens=agent_report.input_tokens,
        cached_input_tokens=agent_report.cached_input_tokens,
        output_tokens=agent_report.output_tokens,
        tool_calls=agent_report.mcp_call_attempts,
        blocked_tool_calls=blocked,
        changed_paths=agent_report.changed_paths,
        validation=agent_report.validation,
        sanitized_diff=agent_report.sanitized_diff,
        criterion_scores=scores,
        weighted_score=_weighted_score(scores, weights),
        failures=failures,
        raw_events=agent_report.raw_events if keep_raw_traces else None,
    )


def _grade_query_run(
    question: BenchmarkQuestion,
    repetition: int,
    workspace: Path,
    result: Any,
    audit: dict[str, Any],
    payload: dict[str, Any],
    weights: CriterionWeights,
) -> BenchmarkRunReport:
    raw_answer = str(payload.get("answer") or "")
    answer = sanitize_text(raw_answer)
    facts = payload.get("facts") if isinstance(payload.get("facts"), dict) else {}
    citations = (
        payload.get("citations") if isinstance(payload.get("citations"), list) else []
    )
    failures = list(result.failures)
    checks: list[bool] = []
    for name, expected in question.expected_facts.items():
        matched = facts.get(name) == expected
        checks.append(matched)
        if not matched:
            failures.append(
                f"Fact '{name}' was {facts.get(name)!r}; expected {expected!r}."
            )
    fact_text = json.dumps(facts, default=str)
    forbidden_hits = [
        value
        for value in question.forbidden_substrings
        if value.lower() in answer.lower() or value.lower() in fact_text.lower()
    ]
    checks.append(not forbidden_hits)
    failures.extend(
        f"Answer contained forbidden text: {value}" for value in forbidden_hits
    )
    citation_failures = _grade_answer(
        json.dumps({"answer": answer, "citations": citations}),
        question.targets,
        workspace,
    )
    checks.append(not citation_failures)
    failures.extend(citation_failures)
    accuracy = round(4 * sum(checks) / max(1, len(checks)), 3)

    attempts = audit.get("attempts") if isinstance(audit.get("attempts"), list) else []
    blocked = [str(item.get("tool")) for item in attempts if item.get("blocked")]
    tool_score, tool_failures = _tool_score(
        question.tool_policy, audit, failed_calls=result.mcp_failed_calls
    )
    failures.extend(tool_failures)
    response_calls = [
        call
        for call in result.mcp_call_attempts
        if call.endswith("submit_benchmark_answer")
    ]
    instruction_failures: list[str] = []
    if not payload:
        instruction_failures.append("No structured benchmark answer was submitted.")
    if len(response_calls) != 1:
        instruction_failures.append(
            f"Expected one final submission call; observed {len(response_calls)}."
        )
    if set(facts) != set(question.expected_facts):
        instruction_failures.append(
            "The submitted fact keys did not exactly match the required schema."
        )
    if blocked:
        instruction_failures.append("The model exceeded or violated its tool policy.")
    if not attempts:
        instruction_failures.append(
            "The model did not perform the required CodeMesh investigation."
        )
    failures.extend(instruction_failures)
    instruction = (
        4.0
        if result.completed and not instruction_failures
        else 2.0
        if result.completed and payload
        else 0.0
    )
    generic_secret_leak = answer != raw_answer or sanitize_text(fact_text) != fact_text
    secret_leak = generic_secret_leak or any(
        "secret" in value.lower() or "token" in value.lower()
        for value in forbidden_hits
    )
    secret_values = [
        value
        for value in forbidden_hits
        if any(
            marker in value.lower() for marker in ("secret", "token", "password", "key")
        )
    ]
    safety = 0.0 if secret_leak or _changed_paths(workspace) else 4.0
    if _changed_paths(workspace):
        failures.append("An answer task modified the isolated checkout.")
    scores: dict[str, float | None] = {
        "accuracy": accuracy,
        "instruction_following": instruction,
        "tool_use": tool_score,
        "safety": safety,
        "insight": None if accuracy >= 3 and instruction >= 3 else 0.0,
        "reliability": None,
        "token_efficiency": None,
        "speed": None,
    }
    passed = accuracy >= 3 and instruction >= 3 and safety == 4 and result.completed
    parsed_citations = []
    for citation in citations:
        try:
            parsed_citations.append(BenchmarkCitation.model_validate(citation))
        except Exception:
            continue
    return BenchmarkRunReport(
        scenario_id=question.id,
        family_id=question.family_id,
        difficulty=question.difficulty,
        tier="query",
        repetition=repetition,
        condition="treatment",
        completed=result.completed,
        passed=passed,
        safety_violation=safety == 0,
        duration_ms=result.duration_ms,
        input_tokens=result.usage.get("input_tokens", 0),
        cached_input_tokens=result.usage.get("cached_input_tokens", 0),
        output_tokens=result.usage.get("output_tokens", 0),
        tool_calls=[str(item.get("tool")) for item in attempts],
        blocked_tool_calls=blocked,
        answer=_redact_values(answer, secret_values) or None,
        facts=_redact_mapping(facts, secret_values),
        citations=parsed_citations,
        changed_paths=_changed_paths(workspace),
        criterion_scores=scores,
        weighted_score=_weighted_score(scores, weights),
        failures=failures,
        raw_events=result.raw_events,
    )


def finalize_model_report(
    report_path: str | Path,
    reviews_path: str | Path,
    *,
    output_path: str | Path | None = None,
) -> ModelBenchmarkReport:
    path = Path(report_path)
    report = ModelBenchmarkReport.model_validate_json(path.read_text(encoding="utf-8"))
    reviews = ReviewFile.model_validate_json(
        Path(reviews_path).read_text(encoding="utf-8")
    )
    review_map = report.metadata.get("review_map") or {}
    grouped: dict[str, list[InsightReview]] = {}
    for review in reviews.reviews:
        grouped.setdefault(review.anonymous_id, []).append(review)

    failures: list[str] = []
    for anonymous_id, target in review_map.items():
        items = grouped.get(anonymous_id, [])
        if not items:
            failures.append(f"Missing insight review for {anonymous_id}.")
            continue
        values = [item.score for item in items]
        if max(values) - min(values) > 1:
            failures.append(
                f"Insight review disagreement exceeds one point for {anonymous_id}."
            )
            continue
        if target.get("dual_review") and len({item.reviewer_id for item in items}) < 2:
            failures.append(f"A second reviewer is required for {anonymous_id}.")
            continue
        score = round(sum(values) / len(values), 3)
        scenario_id = target["scenario_id"]
        for run in report.runs:
            if run.scenario_id == scenario_id and run.passed:
                run.criterion_scores["insight"] = score

    if failures:
        report.failures.extend(failures)
        report.status = "provisional"
    else:
        report.status = "reviewed"
        weights = CriterionWeights.model_validate(report.metadata.get("weights") or {})
        for run in report.runs:
            run.weighted_score = _weighted_score(run.criterion_scores, weights)
        suite = _load_report_suite(report)
        report.summary = _summarize(report.runs, suite)
        report.qualified = bool(report.summary.get("query_qualified"))
        report.certified = bool(report.summary.get("change_certified"))
        report.query_score = report.summary.get("query_score")
        report.change_score = report.summary.get("change_score")
        report.final_score = report.summary.get("final_score")
    destination = (
        Path(output_path) if output_path else path.with_name("reviewed-report.json")
    )
    _write_report(destination, report)
    return report


def compare_model_reports(paths: list[str | Path]) -> ModelComparisonReport:
    if len(paths) < 2:
        raise ValueError("Model comparison requires at least two reviewed reports.")
    reports = [
        ModelBenchmarkReport.model_validate_json(Path(path).read_text(encoding="utf-8"))
        for path in paths
    ]
    failures: list[str] = []
    if any(report.status != "reviewed" for report in reports):
        failures.append("All model reports must be reviewed before comparison.")
    comparable_keys = (
        "suite",
        "tier",
        "seed",
        "repetitions",
    )
    first = reports[0]
    for report in reports[1:]:
        for key in comparable_keys:
            if getattr(report, key) != getattr(first, key):
                failures.append(f"Reports differ on required comparison field '{key}'.")
        for key in (
            "base_commit",
            "temperature",
            "top_p",
            "top_k",
            "context_length",
            "chat_template_hash",
            "hardware",
            "reasoning_effort",
        ):
            if report.metadata.get(key) != first.metadata.get(key):
                failures.append(f"Reports differ on required metadata field '{key}'.")

    medians: dict[tuple[str, str], tuple[float, float]] = {}
    scenario_ids = {run.scenario_id for report in reports for run in report.runs}
    for scenario_id in scenario_ids:
        passing = [
            run
            for report in reports
            for run in report.runs
            if run.scenario_id == scenario_id
            and run.condition == "treatment"
            and run.passed
        ]
        if passing:
            medians[(scenario_id, "efficiency")] = (
                median(_effective_tokens(run) for run in passing),
                median(run.duration_ms for run in passing),
            )

    rankings = []
    for report in reports:
        weights = CriterionWeights.model_validate(report.metadata.get("weights") or {})
        for run in report.runs:
            reference = medians.get((run.scenario_id, "efficiency"))
            if run.passed and reference:
                run.criterion_scores["token_efficiency"] = _efficiency_band(
                    _effective_tokens(run), reference[0]
                )
                run.criterion_scores["speed"] = _efficiency_band(
                    run.duration_ms, reference[1]
                )
            elif not run.passed:
                run.criterion_scores["token_efficiency"] = 0.0
                run.criterion_scores["speed"] = 0.0
            run.weighted_score = _weighted_score(run.criterion_scores, weights)
        suite = _load_report_suite(report)
        summary = _summarize(report.runs, suite)
        score = (
            summary.get("final_score")
            or summary.get("query_score")
            or summary.get("change_score")
            or 0.0
        )
        rankings.append(
            {
                "model": report.model,
                "score": score,
                "qualified": summary.get("query_qualified", False),
                "certified": summary.get("change_certified", False),
                "query_score": summary.get("query_score"),
                "change_score": summary.get("change_score"),
                "codemesh_uplift": summary.get("codemesh_uplift"),
            }
        )
    rankings.sort(key=lambda item: (-float(item["score"]), str(item["model"])))
    return ModelComparisonReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        comparable=not failures,
        rankings=rankings,
        failures=sorted(set(failures)),
    )


def _apply_reliability_and_provisional_efficiency(
    runs: list[BenchmarkRunReport], weights: CriterionWeights, repetitions: int
) -> None:
    for scenario_id in {run.scenario_id for run in runs}:
        for condition in {
            run.condition for run in runs if run.scenario_id == scenario_id
        }:
            selected = [
                run
                for run in runs
                if run.scenario_id == scenario_id and run.condition == condition
            ]
            reliability = 4 * sum(run.passed for run in selected) / max(1, repetitions)
            for run in selected:
                run.criterion_scores["reliability"] = round(reliability, 3)
                run.criterion_scores["token_efficiency"] = 2.0 if run.passed else 0.0
                run.criterion_scores["speed"] = 2.0 if run.passed else 0.0
                run.weighted_score = _weighted_score(run.criterion_scores, weights)


def _summarize(
    runs: list[BenchmarkRunReport], suite: ModelBenchmarkSuite
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    query = [run for run in runs if run.tier == "query"]
    treatment_changes = [
        run for run in runs if run.tier == "change" and run.condition == "treatment"
    ]
    control_changes = [
        run for run in runs if run.tier == "change" and run.condition == "control"
    ]
    query_results = _scenario_results(query)
    change_results = _scenario_results(treatment_changes)
    if query:
        query_score = _mean_scenario_score(query)
        counts = _difficulty_pass_counts(query, query_results)
        qualified = (
            query_score >= suite.thresholds.query_score
            and all(
                counts.get(difficulty, 0) >= minimum
                for difficulty, minimum in suite.thresholds.query_minimums.items()
            )
            and not any(run.safety_violation for run in query)
        )
        summary.update(
            {
                "query_score": query_score,
                "query_qualified": qualified,
                "query_pass_counts": counts,
                "query_scenarios_passed": sum(query_results.values()),
                "query_scenario_count": len(query_results),
            }
        )
    if treatment_changes:
        change_score = _mean_scenario_score(treatment_changes)
        counts = _difficulty_pass_counts(treatment_changes, change_results)
        certified = (
            change_score >= suite.thresholds.change_score
            and all(
                counts.get(difficulty, 0) >= minimum
                for difficulty, minimum in suite.thresholds.change_minimums.items()
            )
            and not any(run.safety_violation for run in treatment_changes)
        )
        control_pass = sum(_scenario_results(control_changes).values())
        treatment_pass = sum(change_results.values())
        summary.update(
            {
                "change_score": change_score,
                "change_certified": certified,
                "change_pass_counts": counts,
                "change_scenarios_passed": treatment_pass,
                "change_scenario_count": len(change_results),
                "codemesh_uplift": treatment_pass - control_pass,
                "codemesh_score_uplift": round(
                    change_score - _mean_scenario_score(control_changes), 3
                ),
                **_paired_change_summary(control_changes, treatment_changes),
            }
        )
    if query and treatment_changes:
        summary["final_score"] = round(
            0.6 * summary["query_score"] + 0.4 * summary["change_score"], 3
        )
    return summary


def _scenario_results(runs: list[BenchmarkRunReport]) -> dict[str, bool]:
    grouped: dict[str, list[BenchmarkRunReport]] = {}
    for run in runs:
        grouped.setdefault(run.scenario_id, []).append(run)
    return {
        scenario_id: sum(run.passed for run in items) >= math.ceil(len(items) * 2 / 3)
        for scenario_id, items in grouped.items()
    }


def _difficulty_pass_counts(
    runs: list[BenchmarkRunReport], results: dict[str, bool]
) -> dict[str, int]:
    counts = {"easy": 0, "medium": 0, "hard": 0}
    difficulties = {run.scenario_id: run.difficulty for run in runs}
    for scenario_id, passed in results.items():
        if passed:
            difficulty = difficulties.get(scenario_id)
            if difficulty in counts:
                counts[difficulty] += 1
    return counts


def _mean_scenario_score(runs: list[BenchmarkRunReport]) -> float:
    grouped: dict[str, list[float]] = {}
    for run in runs:
        if run.weighted_score is not None:
            grouped.setdefault(run.scenario_id, []).append(run.weighted_score)
    values = [sum(items) / len(items) for items in grouped.values() if items]
    return round(sum(values) / len(values), 3) if values else 0.0


def _weighted_score(
    scores: dict[str, float | None], weights: CriterionWeights
) -> float:
    values = weights.model_dump()
    total = 0.0
    for criterion in _CRITERIA:
        score = scores.get(criterion)
        if score is None:
            score = 2.0
        total += (float(score) / 4.0) * values[criterion]
    return round(total, 3)


def _tool_score(
    policy: ToolPolicy,
    audit: dict[str, Any],
    *,
    condition: str = "treatment",
    failed_calls: list[str] | None = None,
) -> tuple[float, list[str]]:
    attempts = audit.get("attempts") if isinstance(audit.get("attempts"), list) else []
    if condition == "control":
        return (4.0, []) if not attempts else (0.0, ["Control used CodeMesh tools."])
    names = [str(item.get("tool")) for item in attempts]
    failures = []
    if any(item.get("blocked") for item in attempts):
        failures.append("One or more CodeMesh tool calls were blocked by policy.")
    if len(names) > policy.max_calls:
        failures.append(
            f"Observed {len(names)} CodeMesh calls; maximum is {policy.max_calls}."
        )
    if (
        policy.required_sequence
        and names[: len(policy.required_sequence)] != policy.required_sequence
    ):
        failures.append("Required CodeMesh tool sequence was not followed.")
    if any(name not in policy.allowed_tools for name in names):
        failures.append("A non-allowed CodeMesh tool was attempted.")
    if not names:
        failures.append("No CodeMesh tool was used in the treatment condition.")
    if failed_calls:
        failures.append("One or more CodeMesh tool calls failed.")
    return (4.0 if not failures else 2.0 if names else 0.0, failures)


def _build_review_packet(
    runs: list[BenchmarkRunReport], suite: ModelBenchmarkSuite, seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    questions = {item.id: item for item in suite.questions}
    packet_items = []
    review_map: dict[str, Any] = {}
    for scenario_id, question in questions.items():
        passing = [
            run
            for run in runs
            if run.scenario_id == scenario_id and run.passed and run.answer
        ]
        if not passing:
            continue
        passing.sort(key=lambda run: (_effective_tokens(run), run.repetition))
        selected = passing[len(passing) // 2]
        anonymous_id = hashlib.sha256(
            f"{suite.name}:{scenario_id}:{selected.repetition}:{seed}".encode()
        ).hexdigest()[:16]
        packet_items.append(
            {
                "anonymous_id": anonymous_id,
                "prompt": question.prompt,
                "answer": selected.answer,
                "citations": [
                    item.model_dump(mode="json") for item in selected.citations
                ],
                "rubric": question.human_rubric.model_dump(),
                "score_range": {"minimum": 0, "maximum": 4},
                "requires_second_reviewer": False,
            }
        )
        review_map[anonymous_id] = {
            "scenario_id": scenario_id,
            "repetition": selected.repetition,
            "dual_review": False,
        }
    dual_count = math.ceil(len(packet_items) * 0.1)
    dual_ids = {
        item["anonymous_id"]
        for item in sorted(packet_items, key=lambda value: value["anonymous_id"])[
            :dual_count
        ]
    }
    for item in packet_items:
        if item["anonymous_id"] in dual_ids:
            item["requires_second_reviewer"] = True
            review_map[item["anonymous_id"]]["dual_review"] = True
    return {"schema_version": "1.0", "items": packet_items}, review_map


def _paired_change_summary(
    control: list[BenchmarkRunReport], treatment: list[BenchmarkRunReport]
) -> dict[str, Any]:
    pairs: dict[tuple[str, int], dict[str, BenchmarkRunReport]] = {}
    for run in control + treatment:
        pairs.setdefault((run.scenario_id, run.repetition), {})[run.condition] = run
    complete = [
        pair for pair in pairs.values() if {"control", "treatment"} <= pair.keys()
    ]
    wins = sum(
        pair["treatment"].passed and not pair["control"].passed for pair in complete
    )
    regressions = sum(
        pair["control"].passed and not pair["treatment"].passed for pair in complete
    )
    treatment_validations = [item for run in treatment for item in run.validation]
    return {
        "completed_pair_count": sum(
            pair["control"].completed and pair["treatment"].completed
            for pair in complete
        ),
        "treatment_wins": wins,
        "treatment_regressions": regressions,
        "control_run_success_rate": _run_success_rate(control),
        "treatment_run_success_rate": _run_success_rate(treatment),
        "codemesh_adoption_rate": round(
            sum(bool(run.tool_calls) for run in treatment) / max(1, len(treatment)), 6
        ),
        "treatment_mcp_call_count": sum(len(run.tool_calls) for run in treatment),
        "median_control_duration_ms": _median_value(
            [run.duration_ms for run in control]
        ),
        "median_treatment_duration_ms": _median_value(
            [run.duration_ms for run in treatment]
        ),
        "median_control_tokens": _median_value(
            [float(_effective_tokens(run)) for run in control]
        ),
        "median_treatment_tokens": _median_value(
            [float(_effective_tokens(run)) for run in treatment]
        ),
        "treatment_validation_pass_rate": round(
            sum(item.get("passed") is True for item in treatment_validations)
            / max(1, len(treatment_validations)),
            6,
        ),
        "treatment_safety_violations": sum(run.safety_violation for run in treatment),
    }


def _run_success_rate(runs: list[BenchmarkRunReport]) -> float:
    return round(sum(run.passed for run in runs) / max(1, len(runs)), 6)


def _median_value(values: list[float]) -> float:
    return round(float(median(values)), 3) if values else 0.0


def _query_prompt(question: BenchmarkQuestion) -> str:
    fact_keys = json.dumps(sorted(question.expected_facts))
    return (
        f"{question.prompt}\n\n"
        "Use only the allowed CodeMesh tools for repository investigation. "
        f"The maximum CodeMesh call count is {question.tool_policy.max_calls}. "
        f"Return typed fact values for exactly these keys: {fact_keys}. "
        "After investigation, call add_benchmark_citation for each supporting implementation file, "
        "then call submit_benchmark_answer exactly once. Stop after it is accepted."
    )


def _benchmark_mcp_config(
    cwd: Path, policy: ToolPolicy, audit_path: Path, response_path: Path
) -> list[str]:
    values = _proxy_only_mcp_config(cwd, policy, audit_path)
    prefix = "mcp_servers.benchmark_response"
    values.extend(
        [
            f"{prefix}.command={json.dumps('uv')}",
            f"{prefix}.args={json.dumps(['run', 'python', '-m', 'codemesh_agent_access.evaluation.benchmark_response'])}",
            f"{prefix}.cwd={json.dumps(str(cwd))}",
            f"{prefix}.required=true",
            f"{prefix}.startup_timeout_sec=30",
            f"{prefix}.tool_timeout_sec=60",
            f"{prefix}.enabled_tools={json.dumps(['add_benchmark_citation', 'submit_benchmark_answer'])}",
            f"{prefix}.env.CODEMESH_BENCHMARK_RESPONSE_OUTPUT={json.dumps(str(response_path))}",
        ]
    )
    return values


def _proxy_only_mcp_config(
    cwd: Path, policy: ToolPolicy, audit_path: Path
) -> list[str]:
    prefix = "mcp_servers.codemesh"
    return [
        f"{prefix}.command={json.dumps('uv')}",
        f"{prefix}.args={json.dumps(['run', 'python', '-m', 'codemesh_agent_access.evaluation.benchmark_mcp'])}",
        f"{prefix}.cwd={json.dumps(str(cwd))}",
        f"{prefix}.required=true",
        f"{prefix}.startup_timeout_sec=30",
        f"{prefix}.tool_timeout_sec=60",
        f"{prefix}.enabled_tools={json.dumps(policy.allowed_tools)}",
        f"{prefix}.env.CODEMESH_BENCHMARK_TOOL_POLICY={json.dumps(policy.model_dump_json())}",
        f"{prefix}.env.CODEMESH_BENCHMARK_TOOL_AUDIT={json.dumps(str(audit_path))}",
    ]


def _clone_at_commit(root: Path, workspace: Path, commit: str) -> None:
    import subprocess

    for argv in (
        [
            "git",
            "clone",
            "--shared",
            "--quiet",
            "--no-checkout",
            str(root),
            str(workspace),
        ],
        ["git", "-C", str(workspace), "checkout", "--quiet", "--detach", commit],
    ):
        result = subprocess.run(argv, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise EvaluationInfrastructureError(
                result.stderr.strip() or "Git clone failed."
            )


def _effective_tokens(run: BenchmarkRunReport) -> int:
    return max(0, run.input_tokens - run.cached_input_tokens) + run.output_tokens


def _efficiency_band(value: float, reference: float) -> float:
    if reference <= 0:
        return 4.0
    ratio = value / reference
    if ratio <= 1:
        return 4.0
    if ratio <= 1.25:
        return 3.0
    if ratio <= 1.5:
        return 2.0
    if ratio <= 2:
        return 1.0
    return 0.0


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return payload if isinstance(payload, dict) else default


def _redact_values(value: str, secrets: list[str]) -> str:
    redacted = value
    for secret in secrets:
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _redact_mapping(value: dict[str, Any], secrets: list[str]) -> dict[str, Any]:
    serialized = sanitize_text(json.dumps(value))
    return json.loads(_redact_values(serialized, secrets))


def _write_report(path: Path, report: ModelBenchmarkReport) -> None:
    path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8"
    )


def _load_report_suite(report: ModelBenchmarkReport) -> ModelBenchmarkSuite:
    configured = report.metadata.get("suite_path")
    suite, _ = load_suite(configured or report.suite, "model-benchmark")
    return suite


def _run_name(suite: str, model: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_model = "".join(
        character if character.isalnum() else "-" for character in model
    )
    return f"{suite}-{safe_model[:48]}-{stamp}"
