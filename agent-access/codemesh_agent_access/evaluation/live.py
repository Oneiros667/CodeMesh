from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .metrics import (
    dotted_value,
    p50,
    percentile,
    ranking_metrics,
    ranking_stability,
    target_matches,
)
from .models import CandidateRecord, LiveCaseReport, LiveReport, LiveSuite


class EvaluationInfrastructureError(RuntimeError):
    pass


class McpEvaluationClient:
    def __init__(
        self,
        command: str | None = None,
        args: list[str] | None = None,
        cwd: str | Path | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        package_root = Path(__file__).resolve().parents[2]
        self.parameters = StdioServerParameters(
            command=command or sys.executable,
            args=args
            or [
                "-m",
                "codemesh_agent_access",
                "mcp",
                "--profile",
                "diagnostic",
            ],
            cwd=Path(cwd) if cwd else package_root,
        )
        self.timeout = timedelta(seconds=timeout_seconds)
        self.session: ClientSession | None = None
        self.startup_ms = 0.0
        self.tool_names: list[str] = []

    @asynccontextmanager
    async def connect(self) -> AsyncIterator["McpEvaluationClient"]:
        started = perf_counter()
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errlog:
            try:
                body_error: BaseException | None = None
                async with stdio_client(self.parameters, errlog=errlog) as (
                    read_stream,
                    write_stream,
                ):
                    async with ClientSession(read_stream, write_stream) as session:
                        self.session = session
                        await session.initialize()
                        tools = await session.list_tools()
                        self.tool_names = sorted(tool.name for tool in tools.tools)
                        self.startup_ms = round((perf_counter() - started) * 1000, 3)
                        try:
                            yield self
                        except BaseException as exc:
                            body_error = exc
                        finally:
                            self.session = None
                if body_error is not None:
                    raise body_error
            except EvaluationInfrastructureError:
                raise
            except Exception as exc:
                raise EvaluationInfrastructureError(
                    f"Could not start or communicate with CodeMesh MCP: {type(exc).__name__}: {exc}"
                ) from exc
            finally:
                self.session = None

    async def call(
        self, tool: str, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], float]:
        if self.session is None:
            raise EvaluationInfrastructureError(
                "The MCP evaluation client is not connected."
            )
        started = perf_counter()
        try:
            result = await self.session.call_tool(
                tool,
                arguments=arguments,
                read_timeout_seconds=self.timeout,
            )
        except Exception as exc:
            raise EvaluationInfrastructureError(
                f"MCP tool '{tool}' failed: {type(exc).__name__}: {exc}"
            ) from exc
        latency_ms = round((perf_counter() - started) * 1000, 3)
        if result.isError:
            raise EvaluationInfrastructureError(
                f"MCP tool '{tool}' returned an error result."
            )
        return _tool_payload(result), latency_ms


async def run_live_evaluation(
    suite: LiveSuite,
    *,
    repository_id: str | None = None,
    repetitions: int = 3,
    warmup: int = 1,
    allow_stale: bool = False,
    keep_raw_traces: bool = False,
    command: str | None = None,
    command_args: list[str] | None = None,
    command_cwd: str | Path | None = None,
) -> LiveReport:
    if repetitions < 1 or warmup < 0:
        raise ValueError("Live evaluation requires repetitions >= 1 and warmup >= 0.")
    started = perf_counter()
    resolved_repository = repository_id or suite.repository_id
    client = McpEvaluationClient(command, command_args, command_cwd)
    tool_source = get_tool_source_identity(Path(client.parameters.cwd))
    tool_source_comparable = bool(tool_source.get("available")) and not bool(
        tool_source.get("working_tree_dirty")
    )
    if not tool_source_comparable and not allow_stale:
        detail = (
            "CodeMesh tool-source checkout is dirty."
            if tool_source.get("available")
            else "CodeMesh tool-source commit identity is unavailable."
        )
        raise EvaluationInfrastructureError(
            f"The MCP implementation is not comparable: {detail}"
        )

    async with client.connect():
        required_tools = {case.tool for case in suite.cases} | {
            "codemesh_status",
            "codemesh_list_repositories",
            "codemesh_get_repository_status",
        }
        missing_tools = sorted(required_tools - set(client.tool_names))
        if missing_tools:
            raise EvaluationInfrastructureError(
                f"CodeMesh MCP is missing required tools: {', '.join(missing_tools)}"
            )

        status_payload, _ = await client.call("codemesh_status", {})
        status = _data(status_payload)
        if not status_payload.get("ok", True) or status.get("status") != "healthy":
            raise EvaluationInfrastructureError("CodeMesh MCP status is not healthy.")

        repositories_payload, _ = await client.call(
            "codemesh_list_repositories", {"limit": 100}
        )
        repositories = _data(repositories_payload).get("repositories", [])
        repository = next(
            (
                item
                for item in repositories
                if isinstance(item, dict)
                and resolved_repository
                in {item.get("repository_id"), item.get("alias")}
            ),
            None,
        )
        if repository is None:
            raise EvaluationInfrastructureError(
                f"Repository '{resolved_repository}' is not listed by CodeMesh."
            )
        canonical_repository_id = str(
            repository.get("repository_id") or resolved_repository
        )

        repository_status_payload, _ = await client.call(
            "codemesh_get_repository_status", {"repository_id": resolved_repository}
        )
        repository_status = _data(repository_status_payload)
        freshness = repository_status.get("freshness") or {}
        fresh = freshness.get("status") == "fresh"
        indexed_commit = freshness.get("indexed_commit")
        suite_commit_matches = (
            suite.repository_commit is None or indexed_commit == suite.repository_commit
        )
        comparable = fresh and suite_commit_matches and tool_source_comparable
        if not comparable and not allow_stale:
            if not fresh:
                detail = (
                    freshness.get("detail") or "Repository freshness is not 'fresh'."
                )
            else:
                detail = (
                    f"Indexed commit {indexed_commit!r} does not match the suite's "
                    f"pinned commit {suite.repository_commit!r}."
                )
            raise EvaluationInfrastructureError(
                f"The indexed repository is not comparable: {detail}"
            )

        case_reports = []
        for case in suite.cases:
            arguments = dict(case.arguments)
            if case.tool != "codemesh_get_tool_guidance":
                arguments.setdefault("repository_id", resolved_repository)
                if not arguments["repository_id"]:
                    arguments["repository_id"] = resolved_repository
            for _ in range(warmup):
                await client.call(case.tool, arguments)
            case_reports.append(
                await _run_live_case(
                    client,
                    case,
                    arguments,
                    repetitions,
                    keep_raw_traces,
                    suite.thresholds.max_primary_rank,
                )
            )

    retrieval_cases = [
        case
        for case, source in zip(case_reports, suite.cases, strict=True)
        if source.targets
    ]
    tool_calls = sum(case.calls for case in case_reports)
    successful_calls = sum(case.successful_calls for case in case_reports)
    secret_leaks = sum(case.secret_leaks for case in case_reports)
    mean_recall = _mean([case.recall_at_k for case in retrieval_cases], default=1.0)
    mean_mrr = _mean([case.reciprocal_rank for case in retrieval_cases], default=1.0)
    success_rate = successful_calls / max(1, tool_calls)
    failures = []
    if success_rate < suite.thresholds.min_tool_success_rate:
        failures.append(
            f"Tool success rate {success_rate:.3f} is below {suite.thresholds.min_tool_success_rate:.3f}."
        )
    if mean_recall < suite.thresholds.min_recall_at_k:
        failures.append(
            f"Mean Recall@k {mean_recall:.3f} is below {suite.thresholds.min_recall_at_k:.3f}."
        )
    if mean_mrr < suite.thresholds.min_mrr:
        failures.append(
            f"Mean MRR {mean_mrr:.3f} is below {suite.thresholds.min_mrr:.3f}."
        )
    if secret_leaks > suite.thresholds.max_secret_leaks:
        failures.append(
            f"Secret leakage count {secret_leaks} exceeds {suite.thresholds.max_secret_leaks}."
        )
    failures.extend(
        f"{case.id}: {failure}" for case in case_reports for failure in case.failures
    )

    diagnostics = [case.diagnostics for case in case_reports if case.diagnostics]
    metadata = {
        "mcp_sdk_version": _package_version("mcp"),
        "python_version": sys.version.split()[0],
        "available_tools": client.tool_names,
        "indexed_commit": freshness.get("indexed_commit"),
        "current_commit": freshness.get("current_commit"),
        "current_branch": freshness.get("current_branch"),
        "working_tree_dirty": freshness.get("working_tree_dirty"),
        "freshness_status": freshness.get("status"),
        "suite_repository_url": suite.repository_url,
        "suite_repository_commit": suite.repository_commit,
        "suite_commit_matches": suite_commit_matches,
        "codemesh_source_commit": tool_source.get("commit"),
        "codemesh_source_branch": tool_source.get("branch"),
        "codemesh_source_checkout_modified": tool_source.get("working_tree_dirty"),
        "search_modes": sorted(
            {str(item.get("mode")) for item in diagnostics if item.get("mode")}
        ),
        "model_providers": sorted(
            {
                str(item.get("model_provider"))
                for item in diagnostics
                if item.get("model_provider")
            }
        ),
    }
    return LiveReport(
        suite=suite.name,
        passed=not failures,
        comparable=comparable,
        generated_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=round((perf_counter() - started) * 1000, 3),
        startup_ms=client.startup_ms,
        repository_id=canonical_repository_id,
        metadata=metadata,
        summary={
            "case_count": len(case_reports),
            "tool_call_count": tool_calls,
            "tool_success_rate": round(success_rate, 6),
            "mean_recall_at_k": round(mean_recall, 6),
            "mean_mrr": round(mean_mrr, 6),
            "mean_ndcg_at_k": round(
                _mean([case.ndcg_at_k for case in retrieval_cases], default=1.0), 6
            ),
            "secret_leaks": secret_leaks,
            "p50_latency_ms": p50(
                [latency for case in case_reports for latency in case.latencies_ms]
            ),
            "p95_latency_ms": percentile(
                [latency for case in case_reports for latency in case.latencies_ms],
                0.95,
            ),
        },
        cases=case_reports,
        failures=failures,
    )


async def get_repository_preflight(
    repository_id: str,
    **client_options: Any,
) -> dict[str, Any]:
    client = McpEvaluationClient(**client_options)
    async with client.connect():
        payload, _ = await client.call(
            "codemesh_get_repository_status", {"repository_id": repository_id}
        )
    data = _data(payload)
    freshness = data.get("freshness") or {}
    if freshness.get("status") != "fresh":
        raise EvaluationInfrastructureError(
            freshness.get("detail")
            or "Agent evaluation requires a fresh CodeMesh index."
        )
    return data


def get_tool_source_identity(path: Path) -> dict[str, Any]:
    def git(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(path), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    try:
        root = git("rev-parse", "--show-toplevel")
        if root.returncode != 0:
            return {"available": False}
        status = git("status", "--porcelain")
        commit = git("rev-parse", "HEAD")
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
    except (OSError, subprocess.SubprocessError):
        return {"available": False}

    if any(result.returncode != 0 for result in (status, commit, branch)):
        return {"available": False}
    return {
        "available": True,
        "commit": commit.stdout.strip(),
        "branch": branch.stdout.strip(),
        "working_tree_dirty": bool(status.stdout.strip()),
    }


async def _run_live_case(
    client: McpEvaluationClient,
    case: Any,
    arguments: dict[str, Any],
    repetitions: int,
    keep_raw_traces: bool,
    max_primary_rank: int,
) -> LiveCaseReport:
    latencies = []
    payloads = []
    rankings = []
    failures = []
    for _ in range(repetitions):
        try:
            payload, latency = await client.call(case.tool, arguments)
        except EvaluationInfrastructureError as exc:
            failures.append(str(exc))
            continue
        latencies.append(latency)
        payloads.append(payload)
        rankings.append(_extract_candidates(_data(payload)))

    data = _data(payloads[0]) if payloads else {}
    candidates = rankings[0] if rankings else []
    metrics = ranking_metrics(candidates, case.targets, case.top_k)
    if len(candidates) < case.min_hit_count:
        failures.append(
            f"Returned {len(candidates)} candidates; expected at least {case.min_hit_count}."
        )
    if any(target.primary for target in case.targets):
        primary_rank = metrics["primary_rank"]
        if primary_rank is None or primary_rank > max_primary_rank:
            failures.append(
                f"Primary target rank is {primary_rank}; expected at most {max_primary_rank}."
            )
    for path, expected in case.expected_values.items():
        actual = dotted_value(data, path)
        if actual != expected:
            failures.append(f"Expected {path}={expected!r}, got {actual!r}.")

    serialized = json.dumps(payloads, sort_keys=True, default=str)
    leaks = sum(serialized.count(secret) for secret in case.forbidden_substrings)
    if leaks:
        failures.append(f"Found {leaks} forbidden substring occurrence(s).")

    relationship_coverage = _relationship_coverage(data, case.relationship_targets)
    if case.relationship_targets and relationship_coverage < 1:
        failures.append(
            f"Relationship coverage is {relationship_coverage:.3f}; expected 1.000."
        )

    diagnostics = (
        data.get("diagnostics") if isinstance(data.get("diagnostics"), dict) else {}
    )
    return LiveCaseReport(
        id=case.id,
        tool=case.tool,
        passed=not failures and len(payloads) == repetitions,
        calls=repetitions,
        successful_calls=len(payloads),
        latencies_ms=latencies,
        p50_latency_ms=p50(latencies),
        p95_latency_ms=percentile(latencies, 0.95),
        hit_count=len(candidates),
        precision_at_k=float(metrics["precision_at_k"]),
        recall_at_k=float(metrics["recall_at_k"]),
        reciprocal_rank=float(metrics["reciprocal_rank"]),
        ndcg_at_k=float(metrics["ndcg_at_k"]),
        ranking_stability=ranking_stability(rankings),
        relationship_coverage=relationship_coverage,
        primary_rank=metrics["primary_rank"],
        secret_leaks=leaks,
        candidates=candidates[: case.top_k],
        diagnostics=diagnostics,
        failures=failures,
        raw_responses=payloads if keep_raw_traces else None,
    )


def _tool_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for content in getattr(result, "content", []):
        text = getattr(content, "text", None)
        if not isinstance(text, str):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise EvaluationInfrastructureError(
        "MCP tool response did not contain a JSON object."
    )


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data", payload)
    return data if isinstance(data, dict) else {}


def _extract_candidates(data: dict[str, Any]) -> list[CandidateRecord]:
    candidates = []
    if isinstance(data.get("hits"), list):
        sources = data["hits"]
    elif isinstance(data.get("items"), list):
        sources = [
            item.get("hit", {}) for item in data["items"] if isinstance(item, dict)
        ]
    elif isinstance(data.get("symbols"), list):
        sources = [
            item.get("node", {}) for item in data["symbols"] if isinstance(item, dict)
        ]
    else:
        sources = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        span = source.get("span") if isinstance(source.get("span"), dict) else {}
        candidates.append(
            CandidateRecord(
                stable_key=source.get("stable_key") or source.get("stableKey"),
                file_path=source.get("file_path")
                or source.get("filePath")
                or span.get("file_path"),
                node_id=source.get("node_id") or source.get("id"),
            )
        )
    return candidates


def _relationship_coverage(data: dict[str, Any], expected: list[Any]) -> float:
    if not expected:
        return 1.0
    items = data.get("items") if isinstance(data.get("items"), list) else []
    matched = 0
    for relationship_target in expected:
        found = False
        for item in items:
            groups = item.get("relationship_groups") if isinstance(item, dict) else None
            relationships = (
                groups.get(relationship_target.group, [])
                if isinstance(groups, dict)
                else []
            )
            for relationship in relationships:
                other = (
                    relationship.get("other", {})
                    if isinstance(relationship, dict)
                    else {}
                )
                span = other.get("span") if isinstance(other.get("span"), dict) else {}
                candidate = CandidateRecord(
                    stable_key=other.get("stable_key") or other.get("stableKey"),
                    file_path=other.get("file_path")
                    or other.get("filePath")
                    or span.get("file_path"),
                    node_id=other.get("node_id") or other.get("id"),
                )
                if target_matches(candidate, relationship_target.target):
                    found = True
                    break
            if found:
                break
        matched += int(found)
    return matched / len(expected)


def _mean(values: list[float], default: float = 0.0) -> float:
    return default if not values else sum(values) / len(values)


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"
