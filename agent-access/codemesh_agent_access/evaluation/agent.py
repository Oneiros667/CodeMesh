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
from typing import Any, Literal

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
    local_provider: Literal["lmstudio", "ollama"] | None = None,
    codex_executable: str = "codex",
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
    if suite.repository_commit and base_commit != suite.repository_commit:
        raise EvaluationInfrastructureError(
            f"Benchmark commit {base_commit!r} does not match the suite's pinned "
            f"commit {suite.repository_commit!r}."
        )

    codex_runner = runner or CodexRunner(codex_executable)
    rng = random.Random(seed)
    mcp_cwd = Path(__file__).resolve().parents[2]
    codemesh_root = _git_root(mcp_cwd)
    if _git(codemesh_root, "status", "--porcelain"):
        raise EvaluationInfrastructureError(
            "Agent evaluation requires a clean CodeMesh tool-source checkout so "
            "the treatment surface has a frozen commit identity."
        )
    codemesh_source_commit = _git(codemesh_root, "rev-parse", "HEAD")
    codemesh_source_branch = _git(codemesh_root, "rev-parse", "--abbrev-ref", "HEAD")
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
                    local_provider=local_provider,
                    reasoning_effort=reasoning_effort,
                    mcp_cwd=mcp_cwd,
                    keep_raw_traces=keep_raw_traces,
                    keep_workspaces=keep_workspaces,
                    runner=codex_runner,
                    artifact_dir=destination,
                    treatment_guidance=suite.treatment_guidance,
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
            "model_provider": local_provider or "default",
            "codex_executable": codex_executable,
            "current_branch": freshness.get("current_branch"),
            "suite_repository_url": suite.repository_url,
            "suite_repository_commit": suite.repository_commit,
            "raw_traces_retained": keep_raw_traces,
            "source_checkout_modified": False,
            "codemesh_source_commit": codemesh_source_commit,
            "codemesh_source_branch": codemesh_source_branch,
            "codemesh_source_checkout_modified": False,
            "classification_requires_codemesh_adoption": True,
            "adoption_mode": "assisted" if suite.treatment_guidance else "spontaneous",
            "prompt_parity": suite.treatment_guidance is None,
            "treatment_guidance": suite.treatment_guidance,
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
    local_provider: Literal["lmstudio", "ollama"] | None,
    reasoning_effort: str,
    mcp_cwd: Path,
    keep_raw_traces: bool,
    keep_workspaces: bool,
    runner: AgentRunner,
    artifact_dir: Path,
    mcp_config: tuple[str, ...] | None = None,
    treatment_guidance: str | None = None,
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
                prompt=_condition_prompt(task.prompt, condition, treatment_guidance),
                cwd=workspace,
                condition=condition,
                model=model,
                local_provider=local_provider,
                reasoning_effort=reasoning_effort,
                sandbox="read-only"
                if task.task_type == "answer"
                else "workspace-write",
                timeout_seconds=task.timeout_seconds,
                mcp_cwd=mcp_cwd,
                output_schema=schema_path if task.task_type == "answer" else None,
                keep_raw_traces=keep_raw_traces,
                mcp_config=mcp_config,
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
            command_violations = _grade_command_policy(task, result.commands)
            if command_violations:
                safety_violation = True
                failures.extend(command_violations)
            diff_check = _run_command(
                ["git", "-C", str(workspace), "diff", "--check"], timeout=30
            )
            if diff_check.returncode != 0:
                failures.append("git diff --check failed.")

        diff = _git(workspace, "diff", "--binary", "HEAD")
        sanitized_diff = sanitize_text(diff) if diff else None
        if diff and sanitized_diff != diff:
            safety_violation = True
            failures.append("Changed content matched the secret scanner.")
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
            mcp_call_attempts=result.mcp_call_attempts,
            mcp_failed_calls=result.mcp_failed_calls,
            command_count=result.command_count,
            command_policy_violations=command_violations
            if task.task_type == "change"
            else [],
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
    adopted_pairs = [pair for pair in completed if bool(pair["treatment"].mcp_calls)]
    attributable_wins = sum(
        pair["treatment"].passed and not pair["control"].passed
        for pair in adopted_pairs
    )
    all_both_pass = [
        pair
        for pair in completed
        if pair["control"].passed and pair["treatment"].passed
    ]
    adopted_both_pass = [
        pair
        for pair in adopted_pairs
        if pair["control"].passed and pair["treatment"].passed
    ]

    control_duration = _median([pair["control"].duration_ms for pair in all_both_pass])
    treatment_duration = _median(
        [pair["treatment"].duration_ms for pair in all_both_pass]
    )
    control_tokens = _median([_tokens(pair["control"]) for pair in all_both_pass])
    treatment_tokens = _median([_tokens(pair["treatment"]) for pair in all_both_pass])
    duration_delta = _relative_delta(control_duration, treatment_duration)
    token_delta = _relative_delta(control_tokens, treatment_tokens)
    codemesh_control_duration = _median(
        [pair["control"].duration_ms for pair in adopted_both_pass]
    )
    codemesh_treatment_duration = _median(
        [pair["treatment"].duration_ms for pair in adopted_both_pass]
    )
    codemesh_control_tokens = _median(
        [_tokens(pair["control"]) for pair in adopted_both_pass]
    )
    codemesh_treatment_tokens = _median(
        [_tokens(pair["treatment"]) for pair in adopted_both_pass]
    )
    codemesh_duration_delta = _relative_delta(
        codemesh_control_duration, codemesh_treatment_duration
    )
    codemesh_token_delta = _relative_delta(
        codemesh_control_tokens, codemesh_treatment_tokens
    )

    if len(completed) < suite.thresholds.minimum_completed_pairs:
        verdict = "insufficient"
    elif safety or regressions > attributable_wins:
        verdict = "regressed"
    elif not adopted_pairs:
        verdict = "neutral"
    elif len(adopted_pairs) < suite.thresholds.minimum_completed_pairs:
        verdict = "insufficient"
    elif attributable_wins > regressions:
        verdict = "improved"
    else:
        threshold = suite.thresholds.efficiency_delta
        improved = (
            codemesh_duration_delta <= -threshold and codemesh_token_delta <= threshold
        ) or (
            codemesh_token_delta <= -threshold and codemesh_duration_delta <= threshold
        )
        regressed = (
            codemesh_duration_delta >= threshold and codemesh_token_delta >= -threshold
        ) or (
            codemesh_token_delta >= threshold and codemesh_duration_delta >= -threshold
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
        "codemesh_attributable_wins": attributable_wins,
        "treatment_regressions": regressions,
        "treatment_safety_violations": safety,
        "control_success_rate": _success_rate(control_runs),
        "treatment_success_rate": _success_rate(treatment_runs),
        "codemesh_adoption_rate": round(adoption, 6),
        "codemesh_adopted_pair_count": len(adopted_pairs),
        "codemesh_efficiency_pair_count": len(adopted_both_pass),
        "median_control_duration_ms": control_duration,
        "median_treatment_duration_ms": treatment_duration,
        "duration_delta": round(duration_delta, 6),
        "median_control_tokens": control_tokens,
        "median_treatment_tokens": treatment_tokens,
        "token_delta": round(token_delta, 6),
        "codemesh_median_control_duration_ms": codemesh_control_duration,
        "codemesh_median_treatment_duration_ms": codemesh_treatment_duration,
        "codemesh_duration_delta": round(codemesh_duration_delta, 6),
        "codemesh_median_control_tokens": codemesh_control_tokens,
        "codemesh_median_treatment_tokens": codemesh_treatment_tokens,
        "codemesh_token_delta": round(codemesh_token_delta, 6),
    }


def _condition_prompt(
    prompt: str, condition: str, treatment_guidance: str | None
) -> str:
    if condition != "treatment" or not treatment_guidance:
        return prompt
    return f"{treatment_guidance.strip()}\n\n{prompt}"


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
        raw_path = str(citation.get("file_path") or "").replace("\\", "/")
        while raw_path.startswith("./"):
            raw_path = raw_path[2:]
        supplied_path = Path(raw_path)
        path = (
            supplied_path.resolve()
            if supplied_path.is_absolute()
            else (workspace / supplied_path).resolve()
        )
        if not path.is_relative_to(workspace.resolve()) or not path.is_file():
            failures.append(f"Citation path does not exist: {raw_path}")
            continue
        relative = path.relative_to(workspace.resolve()).as_posix()
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


def _grade_command_policy(task: Any, commands: list[str]) -> list[str]:
    policy = getattr(task, "command_policy", None)
    if policy is None:
        return []
    failures = []
    if len(commands) > policy.max_commands:
        failures.append(
            f"Agent executed {len(commands)} commands; maximum is {policy.max_commands}."
        )
    for command in commands:
        lowered = command.lower()
        for forbidden in policy.forbidden_substrings:
            if forbidden.lower() in lowered:
                failures.append(f"Agent command violated policy pattern '{forbidden}'.")
    return sorted(set(failures))


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
