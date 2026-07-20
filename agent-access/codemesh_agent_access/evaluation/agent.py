from __future__ import annotations

import asyncio
import fnmatch
import json
import random
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from .codex import AgentRunRequest, AgentRunner, CodexRunner, sanitize_text
from .live import EvaluationInfrastructureError, get_repository_preflight
from .metrics import target_matches
from .models import (
    AgentExecutionReport,
    AgentReport,
    AgentSuite,
    CandidateRecord,
    ValidationCommand,
)


_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "start_line": {"type": "integer", "minimum": 1},
                    "end_line": {"type": "integer", "minimum": 1},
                    "stable_key": {"type": ["string", "null"]},
                },
                "required": ["file_path", "start_line", "end_line", "stable_key"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answer", "citations"],
    "additionalProperties": False,
}


async def run_agent_evaluation(
    suite: AgentSuite,
    suite_path: Path,
    *,
    model: str,
    reasoning_effort: str = "medium",
    repetitions: int = 3,
    seed: int = 42,
    repository_root: str | Path | None = None,
    repository_id: str | None = None,
    output_dir: str | Path | None = None,
    keep_raw_traces: bool = False,
    keep_workspaces: bool = False,
    runner: AgentRunner | None = None,
) -> AgentReport:
    if repetitions < 1:
        raise ValueError("Agent evaluation requires repetitions >= 1.")
    started = perf_counter()
    root = _git_root(Path(repository_root) if repository_root else Path.cwd())
    if _git(root, "status", "--porcelain"):
        raise EvaluationInfrastructureError(
            "Agent evaluation requires a clean source checkout so both conditions use the same commit."
        )
    base_commit = _git(root, "rev-parse", "HEAD")
    resolved_repository = repository_id or suite.repository_id
    preflight = await get_repository_preflight(resolved_repository)
    freshness = preflight.get("freshness") or {}
    if (
        freshness.get("indexed_commit") != base_commit
        or freshness.get("current_commit") != base_commit
    ):
        raise EvaluationInfrastructureError(
            "The CodeMesh indexed commit, repository checkout, and benchmark base commit must match."
        )

    codex_runner = runner or CodexRunner()
    rng = random.Random(seed)
    mcp_cwd = Path(__file__).resolve().parents[2]
    destination = (
        Path(output_dir)
        if output_dir
        else root / ".codemesh-evals" / _run_name(suite.name)
    )
    destination.mkdir(parents=True, exist_ok=False)
    runs: list[AgentExecutionReport] = []

    for task in suite.tasks:
        for repetition in range(1, repetitions + 1):
            conditions = ["control", "treatment"]
            if rng.random() < 0.5:
                conditions.reverse()
            for condition in conditions:
                report = await _run_task_condition(
                    suite_path=suite_path,
                    task=task,
                    repetition=repetition,
                    condition=condition,
                    root=root,
                    base_commit=base_commit,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    mcp_cwd=mcp_cwd,
                    keep_raw_traces=keep_raw_traces,
                    keep_workspaces=keep_workspaces,
                    runner=codex_runner,
                    artifact_dir=destination,
                )
                runs.append(report)

    verdict, summary = classify_agent_results(runs, suite)
    report = AgentReport(
        suite=suite.name,
        model=model,
        reasoning_effort=reasoning_effort,
        seed=seed,
        repetitions=repetitions,
        generated_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=round((perf_counter() - started) * 1000, 3),
        verdict=verdict,
        passed=verdict != "regressed",
        metadata={
            "repository_id": preflight.get("repository_id") or resolved_repository,
            "base_commit": base_commit,
            "current_branch": freshness.get("current_branch"),
            "raw_traces_retained": keep_raw_traces,
            "source_checkout_modified": False,
            "artifact_directory": str(destination.resolve()),
        },
        summary=summary,
        runs=runs,
    )
    (destination / "report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    return report


async def _run_task_condition(
    *,
    suite_path: Path,
    task: Any,
    repetition: int,
    condition: str,
    root: Path,
    base_commit: str,
    model: str,
    reasoning_effort: str,
    mcp_cwd: Path,
    keep_raw_traces: bool,
    keep_workspaces: bool,
    runner: AgentRunner,
    artifact_dir: Path,
) -> AgentExecutionReport:
    temp_parent = Path(tempfile.mkdtemp(prefix="codemesh-eval-"))
    workspace = temp_parent / "workspace"
    try:
        _run_checked(
            [
                "git",
                "clone",
                "--shared",
                "--quiet",
                "--no-checkout",
                str(root),
                str(workspace),
            ]
        )
        _run_checked(
            [
                "git",
                "-C",
                str(workspace),
                "checkout",
                "--quiet",
                "--detach",
                base_commit,
            ]
        )
        if task.setup_patch:
            patch_path = (suite_path.parent / task.setup_patch).resolve()
            if not patch_path.is_file():
                raise EvaluationInfrastructureError(
                    f"Setup patch not found: {patch_path}"
                )
            _run_checked(
                ["git", "-C", str(workspace), "apply", "--check", str(patch_path)]
            )
            _run_checked(["git", "-C", str(workspace), "apply", str(patch_path)])
            _run_checked(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "config",
                    "user.name",
                    "CodeMesh Evaluation",
                ]
            )
            _run_checked(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "config",
                    "user.email",
                    "codemesh-evaluation@example.invalid",
                ]
            )
            _run_checked(["git", "-C", str(workspace), "add", "--all"])
            _run_checked(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "commit",
                    "--quiet",
                    "-m",
                    f"Inject CodeMesh evaluation fault: {task.id}",
                ]
            )

        if task.task_type == "change":
            before = await _run_validations(workspace, task.validation)
            if all(item["passed"] for item in before):
                raise EvaluationInfrastructureError(
                    f"Task '{task.id}' setup did not make any validation command fail."
                )

        schema_path = temp_parent / "answer-schema.json"
        if task.task_type == "answer":
            schema_path.write_text(json.dumps(_ANSWER_SCHEMA), encoding="utf-8")

        result = await runner.run(
            AgentRunRequest(
                prompt=task.prompt,
                cwd=workspace,
                condition=condition,
                model=model,
                reasoning_effort=reasoning_effort,
                sandbox="read-only"
                if task.task_type == "answer"
                else "workspace-write",
                timeout_seconds=task.timeout_seconds,
                mcp_cwd=mcp_cwd,
                output_schema=schema_path if task.task_type == "answer" else None,
                keep_raw_traces=keep_raw_traces,
            )
        )

        failures = list(result.failures)
        validation: list[dict[str, Any]] = []
        changed_paths = _changed_paths(workspace)
        safety_violation = False
        if task.task_type == "answer":
            failures.extend(
                _grade_answer(result.final_message, task.targets, workspace)
            )
        else:
            validation = await _run_validations(workspace, task.validation)
            failures.extend(
                f"Validation failed: {' '.join(item['argv'])}"
                for item in validation
                if not item["passed"]
            )
            scope_failures, safety_violation = _grade_change_scope(task, changed_paths)
            failures.extend(scope_failures)
            diff_check = _run_command(
                ["git", "-C", str(workspace), "diff", "--check"], timeout=30
            )
            if diff_check.returncode != 0:
                failures.append("git diff --check failed.")

        diff = _git(workspace, "diff", "--binary", "HEAD")
        sanitized_diff = sanitize_text(diff) if diff else None
        run_report = AgentExecutionReport(
            task_id=task.id,
            repetition=repetition,
            condition=condition,
            completed=result.completed,
            passed=result.completed and not failures,
            safety_violation=safety_violation,
            duration_ms=result.duration_ms,
            input_tokens=result.usage.get("input_tokens", 0),
            cached_input_tokens=result.usage.get("cached_input_tokens", 0),
            output_tokens=result.usage.get("output_tokens", 0),
            reasoning_output_tokens=result.usage.get("reasoning_output_tokens", 0),
            mcp_calls=result.mcp_calls,
            command_count=result.command_count,
            file_change_count=result.file_change_count,
            changed_paths=changed_paths,
            validation=validation,
            failures=failures,
            sanitized_diff=sanitized_diff,
            raw_events=result.raw_events if keep_raw_traces else None,
            final_message=result.final_message if keep_raw_traces else None,
        )
        if keep_raw_traces:
            run_dir = artifact_dir / f"{task.id}-{repetition}-{condition}"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(event) for event in result.raw_events),
                encoding="utf-8",
            )
            (run_dir / "final-message.txt").write_text(
                result.final_message, encoding="utf-8"
            )
            (run_dir / "changes.diff").write_text(diff, encoding="utf-8")
        if keep_workspaces:
            retained = (
                artifact_dir / "workspaces" / f"{task.id}-{repetition}-{condition}"
            )
            retained.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(workspace), retained)
        return run_report
    finally:
        if temp_parent.exists():
            shutil.rmtree(temp_parent)


def classify_agent_results(
    runs: list[AgentExecutionReport], suite: AgentSuite
) -> tuple[str, dict[str, Any]]:
    by_pair: dict[tuple[str, int], dict[str, AgentExecutionReport]] = {}
    for run in runs:
        by_pair.setdefault((run.task_id, run.repetition), {})[run.condition] = run
    pairs = [pair for pair in by_pair.values() if {"control", "treatment"} <= set(pair)]
    completed = [
        pair
        for pair in pairs
        if pair["control"].completed and pair["treatment"].completed
    ]
    wins = sum(
        pair["treatment"].passed and not pair["control"].passed for pair in completed
    )
    regressions = sum(
        pair["control"].passed and not pair["treatment"].passed for pair in completed
    )
    safety = sum(pair["treatment"].safety_violation for pair in completed)
    both_pass = [
        pair
        for pair in completed
        if pair["control"].passed and pair["treatment"].passed
    ]

    control_duration = _median([pair["control"].duration_ms for pair in both_pass])
    treatment_duration = _median([pair["treatment"].duration_ms for pair in both_pass])
    control_tokens = _median([_tokens(pair["control"]) for pair in both_pass])
    treatment_tokens = _median([_tokens(pair["treatment"]) for pair in both_pass])
    duration_delta = _relative_delta(control_duration, treatment_duration)
    token_delta = _relative_delta(control_tokens, treatment_tokens)

    if len(completed) < suite.thresholds.minimum_completed_pairs:
        verdict = "insufficient"
    elif safety or regressions > wins:
        verdict = "regressed"
    elif wins > regressions:
        verdict = "improved"
    else:
        threshold = suite.thresholds.efficiency_delta
        improved = (duration_delta <= -threshold and token_delta <= threshold) or (
            token_delta <= -threshold and duration_delta <= threshold
        )
        regressed = (duration_delta >= threshold and token_delta >= -threshold) or (
            token_delta >= threshold and duration_delta >= -threshold
        )
        verdict = "improved" if improved else "regressed" if regressed else "neutral"

    treatment_runs = [run for run in runs if run.condition == "treatment"]
    control_runs = [run for run in runs if run.condition == "control"]
    adoption = sum(bool(run.mcp_calls) for run in treatment_runs) / max(
        1, len(treatment_runs)
    )
    return verdict, {
        "pair_count": len(pairs),
        "completed_pair_count": len(completed),
        "treatment_wins": wins,
        "treatment_regressions": regressions,
        "treatment_safety_violations": safety,
        "control_success_rate": _success_rate(control_runs),
        "treatment_success_rate": _success_rate(treatment_runs),
        "codemesh_adoption_rate": round(adoption, 6),
        "median_control_duration_ms": control_duration,
        "median_treatment_duration_ms": treatment_duration,
        "duration_delta": round(duration_delta, 6),
        "median_control_tokens": control_tokens,
        "median_treatment_tokens": treatment_tokens,
        "token_delta": round(token_delta, 6),
    }


def _grade_answer(message: str, targets: list[Any], workspace: Path) -> list[str]:
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return ["Final answer was not valid structured JSON."]
    citations = payload.get("citations") if isinstance(payload, dict) else None
    if not isinstance(citations, list):
        return ["Final answer did not contain a citations array."]
    candidates = []
    failures = []
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        relative = str(citation.get("file_path") or "").replace("\\", "/").lstrip("./")
        path = (workspace / relative).resolve()
        if not path.is_relative_to(workspace.resolve()) or not path.is_file():
            failures.append(f"Citation path does not exist: {relative}")
            continue
        try:
            start_line = int(citation.get("start_line"))
            end_line = int(citation.get("end_line"))
        except (TypeError, ValueError):
            failures.append(f"Citation has invalid line numbers: {relative}")
            continue
        line_count = len(
            path.read_text(encoding="utf-8", errors="replace").splitlines()
        )
        if start_line < 1 or end_line < start_line or end_line > max(1, line_count):
            failures.append(
                f"Citation line range is outside the file: {relative}:{start_line}-{end_line}"
            )
            continue
        candidates.append(
            CandidateRecord(
                file_path=relative,
                stable_key=citation.get("stable_key"),
            )
        )
    for target in targets:
        if not any(target_matches(candidate, target) for candidate in candidates):
            failures.append(
                f"Answer did not cite required target {target.file_path or target.stable_key or target.node_id}."
            )
    return failures


def _grade_change_scope(task: Any, changed_paths: list[str]) -> tuple[list[str], bool]:
    failures = []
    safety = False
    for pattern in task.required_changed_paths:
        if not any(fnmatch.fnmatch(path, pattern) for path in changed_paths):
            failures.append(f"No changed path matched required pattern '{pattern}'.")
    if task.allowed_changed_paths:
        outside = [
            path
            for path in changed_paths
            if not any(
                fnmatch.fnmatch(path, pattern) for pattern in task.allowed_changed_paths
            )
        ]
        if outside:
            safety = True
            failures.append(
                f"Changed paths outside the allowlist: {', '.join(outside)}"
            )
    forbidden = [
        path
        for path in changed_paths
        if any(
            fnmatch.fnmatch(path, pattern) for pattern in task.forbidden_changed_paths
        )
    ]
    if forbidden:
        safety = True
        failures.append(f"Changed forbidden paths: {', '.join(forbidden)}")
    return failures, safety


async def _run_validations(
    workspace: Path, commands: list[ValidationCommand]
) -> list[dict[str, Any]]:
    reports = []
    for command in commands:
        cwd = (workspace / command.cwd).resolve()
        if not cwd.is_relative_to(workspace.resolve()):
            raise EvaluationInfrastructureError(
                f"Validation working directory escapes the workspace: {command.cwd}"
            )
        result = await asyncio.to_thread(
            _run_command, command.argv, cwd, command.timeout_seconds
        )
        output = sanitize_text((result.stdout or "") + (result.stderr or ""))[-4000:]
        reports.append(
            {
                "argv": command.argv,
                "cwd": command.cwd,
                "exit_code": result.returncode,
                "passed": result.returncode == 0,
                "output_tail": output,
            }
        )
    return reports


def _changed_paths(workspace: Path) -> list[str]:
    result = _run_command(
        ["git", "-C", str(workspace), "status", "--porcelain"], timeout=30
    )
    if result.returncode != 0:
        raise EvaluationInfrastructureError(
            "Could not inspect benchmark workspace changes."
        )
    status = result.stdout
    paths = []
    for line in status.splitlines():
        value = line[3:].strip()
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        if value:
            paths.append(value.replace("\\", "/"))
    return sorted(set(paths))


def _git_root(start: Path) -> Path:
    result = _run_command(
        ["git", "-C", str(start.resolve()), "rev-parse", "--show-toplevel"], timeout=10
    )
    if result.returncode != 0:
        raise EvaluationInfrastructureError(
            f"Could not resolve Git root from '{start}'."
        )
    return Path(result.stdout.strip()).resolve()


def _git(root: Path, *args: str) -> str:
    result = _run_command(["git", "-C", str(root), *args], timeout=30)
    if result.returncode != 0:
        raise EvaluationInfrastructureError(
            f"git {' '.join(args)} failed: {sanitize_text(result.stderr)[-1000:]}"
        )
    return result.stdout.strip()


def _run_checked(argv: list[str]) -> None:
    result = _run_command(argv, timeout=120)
    if result.returncode != 0:
        raise EvaluationInfrastructureError(
            f"Command failed: {' '.join(argv)}\n{sanitize_text(result.stderr)[-2000:]}"
        )


def _run_command(
    argv: list[str], cwd: Path | None = None, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EvaluationInfrastructureError(
            f"Could not run {' '.join(argv)}: {type(exc).__name__}: {exc}"
        ) from exc


def _tokens(run: AgentExecutionReport) -> float:
    return float(run.input_tokens + run.output_tokens + run.reasoning_output_tokens)


def _median(values: list[float]) -> float:
    return round(float(median(values)), 3) if values else 0.0


def _relative_delta(control: float, treatment: float) -> float:
    if control <= 0:
        return 0.0 if treatment <= 0 else 1.0
    return (treatment - control) / control


def _success_rate(runs: list[AgentExecutionReport]) -> float:
    return round(sum(run.passed for run in runs) / max(1, len(runs)), 6)


def _run_name(suite: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in suite
    )
    return f"{safe}-{stamp}"
