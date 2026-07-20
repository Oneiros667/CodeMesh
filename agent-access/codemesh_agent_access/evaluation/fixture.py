from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .. import mcp, tools
from ..models import (
    ContextHit,
    ContextPackageItem,
    ContextPackageQuery,
    ContextPackageResponse,
    ContextQuery,
    ContextResponse,
    HealthResponse,
    IngestionRunListResponse,
    IngestionRunSummary,
    NodeLookup,
    NodeResponse,
    NodeSummaryCoverageResponse,
    RepositoryStatusResponse,
    RepositorySummary,
)


@dataclass(frozen=True)
class EvaluationCaseResult:
    name: str
    passed: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True)
class EvaluationReport:
    suite: str
    passed: bool
    generated_at: datetime
    cases: list[EvaluationCaseResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "passed": self.passed,
            "generated_at": self.generated_at.isoformat(),
            "cases": [case.to_dict() for case in self.cases],
        }


async def run_mcp_evaluations() -> EvaluationReport:
    fixture_store = FixtureEvaluationStore()
    original_get_store = tools.get_store
    tools.get_store = lambda: fixture_store

    try:
        server = mcp.build_server()
        cases = [
            await _run_case(
                "tool guidance recommends freshness checks",
                lambda: _evaluate_tool_guidance(server),
            ),
            await _run_case(
                "context search returns diagnostics and stable hits",
                lambda: _evaluate_context_search(server),
            ),
            await _run_case(
                "context package includes agent-ready metadata",
                lambda: _evaluate_context_package(server),
            ),
            await _run_case(
                "repository status exposes stale refresh guidance",
                lambda: _evaluate_repository_status(server),
            ),
            await _run_case(
                "context package does not expose fixture secrets",
                lambda: _evaluate_secret_redaction(server),
            ),
        ]
    finally:
        tools.get_store = original_get_store

    return EvaluationReport(
        suite="mcp-fixture",
        passed=all(case.passed for case in cases),
        generated_at=datetime.now(timezone.utc),
        cases=cases,
    )


async def _run_case(
    name: str, run: Callable[[], Awaitable[None]]
) -> EvaluationCaseResult:
    try:
        await run()
    except AssertionError as exc:
        return EvaluationCaseResult(name=name, passed=False, message=str(exc))
    except Exception as exc:  # pragma: no cover - defensive report path
        return EvaluationCaseResult(
            name=name,
            passed=False,
            message=f"{type(exc).__name__}: {exc}",
        )

    return EvaluationCaseResult(name=name, passed=True)


async def _evaluate_tool_guidance(server: Any) -> None:
    _content, structured = await server.call_tool(
        "codemesh_get_tool_guidance",
        {"task": "check whether repository context is stale before editing"},
    )
    data = structured["data"]

    assert data["recommended_workflows"], "No workflows were recommended."
    assert data["recommended_workflows"][0]["id"] == "check_freshness", (
        "Freshness workflow was not ranked first."
    )
    assert "codemesh_get_repository_status" in data["available_tools"], (
        "Repository status tool is missing from guidance."
    )


async def _evaluate_context_search(server: Any) -> None:
    _content, structured = await server.call_tool(
        "codemesh_search_context",
        {
            "query": "refresh workflow",
            "repository_id": "code_mesh",
            "limit": 3,
            "include_context_relationships": True,
        },
    )
    data = structured["data"]

    assert data["hits"], "Search returned no hits."
    assert data["hits"][0]["stable_key"] == "CodeMeshRefreshWorkflow.ResolveTarget", (
        "Expected refresh workflow hit was not ranked first."
    )
    assert data["diagnostics"]["hit_count"] == 1, "Unexpected search hit count."
    assert data["diagnostics"]["lexical_fallback"] is False, (
        "Search incorrectly reported lexical fallback."
    )


async def _evaluate_context_package(server: Any) -> None:
    _content, structured = await server.call_tool(
        "codemesh_get_context_package",
        {
            "query": "refresh workflow",
            "repository_id": "code_mesh",
            "limit": 2,
            "max_characters": 5000,
            "output_format": "agent",
        },
    )
    data = structured["data"]
    agent_text = structured["agent_text"]

    assert data["items"], "Context package returned no items."
    assert data["items"][0]["hit"]["content_hash"], "Package item lacks content hash."
    assert data["items"][0]["relationship_groups"]["contains"], (
        "Package item lacks grouped relationships."
    )
    assert data["validation_recommendations"], (
        "Package lacks validation recommendations."
    )
    assert "Validation:" in agent_text, "Agent text omits validation guidance."
    assert "Stable key:" in agent_text, "Agent text omits stable keys."
    assert "Snippet:" in agent_text, "Agent text omits snippets."


async def _evaluate_repository_status(server: Any) -> None:
    _content, structured = await server.call_tool(
        "codemesh_get_repository_status",
        {"repository_id": "code_mesh"},
    )
    data = structured["data"]

    assert data["repository_id"] == "repo:codemesh", (
        "Repository alias was not resolved."
    )
    assert data["freshness"]["is_stale"] is True, "Fixture should report stale context."
    assert data["refresh"]["status"] == "completed", "Latest refresh status changed."
    assert "codemesh refresh" in data["refresh"]["recommended_action"], (
        "Refresh guidance is missing."
    )


async def _evaluate_secret_redaction(server: Any) -> None:
    _content, structured = await server.call_tool(
        "codemesh_get_context_package",
        {
            "query": "secret handling",
            "repository_id": "code_mesh",
            "limit": 2,
            "max_characters": 5000,
            "output_format": "agent",
        },
    )
    serialized = str(structured)

    assert "super-secret-token" not in serialized, "Fixture secret leaked."
    assert "[REDACTED]" in serialized, "Redaction marker is missing."


class FixtureEvaluationStore:
    repository = RepositorySummary(
        repository_id="repo:codemesh",
        alias="code_mesh",
        root_path="D:/source/repos/CodeMesh",
        branch="main",
        commit="old-indexed-commit",
        last_run_id="run:codemesh-eval",
        last_stage="Completed",
        node_count=4,
        relationship_count=2,
        content_count=2,
        embedding_count=0,
        metadata={"language": "csharp"},
    )
    latest_run = IngestionRunSummary(
        run_id="run:codemesh-eval",
        repository_id="repo:codemesh",
        repository_root="D:/source/repos/CodeMesh",
        stage="Completed",
        language="csharp",
        parser_name="CodeMesh.Parser.CSharp",
        skip_embeddings=True,
        embedding_provider="none",
        embedding_model="none",
        node_count=4,
        relationship_count=2,
        content_count=2,
        stats={
            "parsed_node_count": 4,
            "written_node_count": 1,
            "written_relationship_count": 1,
            "written_content_count": 1,
            "written_embedding_count": 0,
            "written_summary_count": 0,
        },
    )

    async def health(self) -> HealthResponse:
        return HealthResponse(
            status="healthy",
            components={"fixture": {"status": "healthy"}},
        )

    async def search_context(self, query: ContextQuery) -> ContextResponse:
        hit = _fixture_hit(query.repository_id or "repo:codemesh")
        return ContextResponse(
            query=query,
            hits=[hit],
            diagnostics={
                "mode": "lexical",
                "embedding_attempted": False,
                "embedding_source": "none",
                "model_provider": "none",
                "vector_available": False,
                "vector_hit_count": 0,
                "lexical_hit_count": 1,
                "summary_hit_count": 0,
                "vector_candidate_count": 0,
                "lexical_candidate_count": 1,
                "summary_candidate_count": 0,
                "lexical_fallback": False,
                "hit_count": 1,
            },
        )

    async def get_context_package(
        self, query: ContextPackageQuery
    ) -> ContextPackageResponse:
        hit = _fixture_hit(query.repository_id or "repo:codemesh")
        content = {
            "hash": "content:refresh-workflow",
            "text": "public static CodeMeshRefreshTarget ResolveTarget(...) { return target; }",
            "metadata": {"redaction": "[REDACTED]"},
        }
        if "secret" in query.query.lower():
            content["text"] = "CODEMESH_TOKEN=[REDACTED]"

        item = ContextPackageItem(
            hit=hit,
            node={
                "id": hit.node_id,
                "name": "ResolveTarget",
                "kind": "Method",
                "span": {
                    "file_path": hit.file_path,
                    "start_line": hit.start_line,
                    "end_line": hit.end_line,
                },
            },
            content={"hash": hit.content_hash, "metadata": content["metadata"]},
            snippet=content["text"],
            relationships=[
                {
                    "kind": "CONTAINS",
                    "direction": "out",
                    "other": {
                        "node_id": "node:refresh-target",
                        "name": "CodeMeshRefreshTarget",
                        "kind": "Record",
                        "file_path": "src/CodeMesh.Control/Configuration/CodeMeshRefreshWorkflow.cs",
                        "start_line": 3,
                        "end_line": 3,
                    },
                }
            ],
            relationship_groups={
                "contains": [
                    {
                        "kind": "CONTAINS",
                        "direction": "out",
                        "other": {
                            "node_id": "node:refresh-target",
                            "name": "CodeMeshRefreshTarget",
                            "kind": "Record",
                            "file_path": "src/CodeMesh.Control/Configuration/CodeMeshRefreshWorkflow.cs",
                            "start_line": 3,
                            "end_line": 3,
                        },
                    }
                ]
            },
            rationale={
                "rank": 1,
                "score": hit.score,
                "score_components": hit.score_components,
                "expanded": False,
            },
        )

        return ContextPackageResponse(
            query=query,
            repository=self.repository.model_dump(mode="json"),
            latest_run=self.latest_run.model_dump(mode="json"),
            items=[item],
            validation_recommendations=[
                {
                    "command": "dotnet run --project tests/CodeMesh.Tests",
                    "reason": ".NET implementation context is included",
                    "applies_to": [hit.file_path],
                }
            ],
            total_snippet_characters=len(item.snippet or ""),
        )

    async def get_node(self, lookup: NodeLookup) -> NodeResponse:
        hit = _fixture_hit(lookup.repository_id or "repo:codemesh")
        return NodeResponse(
            node={
                "id": lookup.node_id,
                "name": "ResolveTarget",
                "kind": "Method",
                "span": {
                    "file_path": hit.file_path,
                    "start_line": hit.start_line,
                    "end_line": hit.end_line,
                },
            },
            content={"hash": hit.content_hash, "text": "fixture"},
        )

    async def get_repository(self, repository_id: str) -> RepositorySummary | None:
        if repository_id in {"code_mesh", "repo:codemesh"}:
            return self.repository
        return None

    async def list_ingestion_runs(
        self, repository_id: str | None = None, limit: int = 50
    ) -> IngestionRunListResponse:
        return IngestionRunListResponse(runs=[self.latest_run][:limit])

    async def get_repository_status(
        self, repository_id: str
    ) -> RepositoryStatusResponse:
        return RepositoryStatusResponse(
            repository_id="repo:codemesh",
            repository=self.repository,
            latest_run=self.latest_run,
            summary_coverage=NodeSummaryCoverageResponse(repository_id="repo:codemesh"),
            counts={
                "nodes": 4,
                "relationships": 2,
                "content": 2,
                "vectors": 0,
                "summaries": 0,
            },
            freshness={
                "status": "stale",
                "is_stale": True,
                "indexed_commit": "old-indexed-commit",
                "current_commit": "new-working-commit",
            },
            refresh={
                "status": "completed",
                "changed": True,
                "latest_run_id": self.latest_run.run_id,
                "recommended_action": "Run `codemesh refresh --skip-embeddings`.",
            },
        )


def _fixture_hit(repository_id: str) -> ContextHit:
    return ContextHit(
        node_id="node:refresh-resolve-target",
        stable_key="CodeMeshRefreshWorkflow.ResolveTarget",
        kind="Method",
        file_path="src/CodeMesh.Control/Configuration/CodeMeshRefreshWorkflow.cs",
        start_line=5,
        end_line=18,
        score=0.98,
        repository_id="repo:codemesh"
        if repository_id == "code_mesh"
        else repository_id,
        content_hash="content:refresh-workflow",
        score_components={"lexical_score": 0.98},
        preview="Resolve the repository root and default solution for refresh.",
    )
