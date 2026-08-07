from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from typing import Any, Callable, Literal

from mcp.types import CallToolResult, TextContent

from . import tools
from .formatting import format_context_package_for_agent


_TOOL_NAMES = [
    "codemesh_status",
    "codemesh_get_tool_guidance",
    "codemesh_search_context",
    "codemesh_get_context_package",
    "codemesh_search_symbols",
    "codemesh_get_node",
    "codemesh_get_neighbors",
    "codemesh_list_repositories",
    "codemesh_get_repository",
    "codemesh_get_repository_status",
    "codemesh_delete_repository",
    "codemesh_get_summary_coverage",
    "codemesh_list_ingestion_runs",
]

_MAX_MCP_AGENT_CHARACTERS = 12000

_SEARCH_CONTEXT_ARGUMENTS: dict[str, dict[str, Any]] = {
    "query": {"type": "string", "required": True},
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "limit": {"type": "integer", "default": 8},
    "kinds": {"type": "string[]|null", "default": None},
    "filters": {"type": "object|null", "default": None},
    "vector": {"type": "number[]|null", "default": None},
    "expand_context": {"type": "boolean", "default": True},
    "context_depth": {"type": "integer", "default": 4},
    "include_context_relationships": {"type": "boolean", "default": False},
    "context_relationship_limit": {"type": "integer", "default": 8},
}

_TOOL_GUIDANCE_ARGUMENTS: dict[str, dict[str, Any]] = {
    "task": {
        "type": "string|null",
        "default": None,
        "description": "Optional natural-language task to rank CodeMesh tool workflows.",
    },
}

_CONTEXT_PACKAGE_ARGUMENTS: dict[str, dict[str, Any]] = {
    "query": {"type": "string", "required": True},
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "limit": {"type": "integer", "default": 8},
    "max_characters": {"type": "integer", "default": 12000},
    "kinds": {"type": "string[]|null", "default": None},
    "filters": {"type": "object|null", "default": None},
    "vector": {"type": "number[]|null", "default": None},
    "context_depth": {"type": "integer", "default": 4},
    "include_content": {"type": "boolean", "default": True},
    "include_relationships": {"type": "boolean", "default": True},
    "relationship_limit": {"type": "integer", "default": 8},
    "caller_limit": {"type": "integer|null", "default": None},
    "callee_limit": {"type": "integer|null", "default": None},
    "read_limit": {"type": "integer|null", "default": None},
    "write_limit": {"type": "integer|null", "default": None},
    "contains_limit": {"type": "integer|null", "default": None},
    "definition_limit": {"type": "integer|null", "default": None},
    "uses_type_limit": {"type": "integer|null", "default": None},
    "include_repository": {"type": "boolean", "default": True},
    "output_format": {"type": "string", "default": "json", "values": ["json", "agent"]},
}

_SYMBOL_SEARCH_ARGUMENTS: dict[str, dict[str, Any]] = {
    "query": {"type": "string", "required": True},
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "limit": {"type": "integer", "default": 20},
    "kinds": {"type": "string[]|null", "default": None},
    "filters": {"type": "object|null", "default": None},
    "include_declarations": {"type": "boolean", "default": True},
}

_NODE_ARGUMENTS: dict[str, dict[str, Any]] = {
    "node_id": {"type": "string", "required": True},
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "include_content": {"type": "boolean", "default": True},
    "include_neighbors": {"type": "boolean", "default": True},
}

_NEIGHBOR_ARGUMENTS: dict[str, dict[str, Any]] = {
    "node_id": {"type": "string", "required": True},
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "depth": {"type": "integer", "default": 1},
    "relationship_kinds": {"type": "string[]|null", "default": None},
}

_LIST_REPOSITORIES_ARGUMENTS: dict[str, dict[str, Any]] = {
    "limit": {"type": "integer", "default": 50},
}

_GET_REPOSITORY_ARGUMENTS: dict[str, dict[str, Any]] = {
    "repository_id": {
        "type": "string",
        "required": True,
        "description": "Repository hash id or alias.",
    },
}

_GET_REPOSITORY_STATUS_ARGUMENTS: dict[str, dict[str, Any]] = {
    "repository_id": {
        "type": "string",
        "required": True,
        "description": "Repository hash id or alias.",
    },
}

_DELETE_REPOSITORY_ARGUMENTS: dict[str, dict[str, Any]] = {
    "repository_id": {
        "type": "string",
        "required": True,
        "description": "Repository hash id or alias.",
    },
    "confirm": {
        "type": "boolean",
        "default": False,
        "description": "Must be true to delete indexed repository data.",
    },
}

_SUMMARY_COVERAGE_ARGUMENTS: dict[str, dict[str, Any]] = {
    "repository_id": {
        "type": "string",
        "required": True,
        "description": "Repository hash id or alias.",
    },
}

_LIST_RUNS_ARGUMENTS: dict[str, dict[str, Any]] = {
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "limit": {"type": "integer", "default": 50},
}

_RELATIONSHIP_GROUPS = [
    "callers",
    "callees",
    "reads",
    "writes",
    "contains",
    "defines",
    "uses_types",
]

_TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "codemesh_status": {
        "description": "Return CodeMesh Agent Access health and configured read endpoints.",
        "arguments": {},
    },
    "codemesh_get_tool_guidance": {
        "description": "Start here when deciding how CodeMesh can reduce repository exploration. Maps implementation discovery, change impact, validation selection, freshness, and symbol lookup to read-only workflows.",
        "arguments": _TOOL_GUIDANCE_ARGUMENTS,
        "response": {
            "fields": [
                "task",
                "recommended_workflows",
                "available_tools",
                "default_start",
            ],
        },
    },
    "codemesh_search_context": {
        "description": "Start here for broad source-grounded implementation discovery in an indexed repository. Rank relevant code and docs from natural-language task text before broad shell searches; use codemesh_get_context_package when relationships or validation are needed.",
        "arguments": _SEARCH_CONTEXT_ARGUMENTS,
        "response": {
            "diagnostics": [
                "mode",
                "embedding_attempted",
                "embedding_source",
                "model_provider",
                "vector_available",
                "vector_hit_count",
                "lexical_hit_count",
                "summary_hit_count",
                "vector_candidate_count",
                "lexical_candidate_count",
                "summary_candidate_count",
                "lexical_fallback",
                "hit_count",
            ],
        },
    },
    "codemesh_get_context_package": {
        "description": "Start here for implementation discovery, likely change-impact analysis, or validation selection in an indexed repository. Returns ranked snippets, graph relationships, freshness metadata, and repository-scoped validation recommendations. Agent format is capped at 12,000 characters; start with defaults, then verify returned file spans with targeted reads instead of duplicating broad repository exploration.",
        "arguments": _CONTEXT_PACKAGE_ARGUMENTS,
        "response": {
            "relationship_groups": list(_RELATIONSHIP_GROUPS),
            "fields": [
                "query",
                "repository",
                "latest_run",
                "items",
                "validation_recommendations",
                "total_snippet_characters",
                "generated_at",
            ],
            "output_formats": ["json", "agent"],
            "agent_content_type": "text",
            "agent_max_characters": _MAX_MCP_AGENT_CHARACTERS,
        },
    },
    "codemesh_search_symbols": {
        "description": "Use when a class, method, function, file, endpoint, or symbol-like name is known.",
        "arguments": _SYMBOL_SEARCH_ARGUMENTS,
    },
    "codemesh_get_node": {
        "description": "Use after search or symbol lookup when the exact node id is known and content or immediate relationships are needed.",
        "arguments": _NODE_ARGUMENTS,
    },
    "codemesh_get_neighbors": {
        "description": "Use for likely change-impact analysis around a known node. Inspect callers, callees, reads, writes, containment, and other indexed relationships.",
        "arguments": _NEIGHBOR_ARGUMENTS,
    },
    "codemesh_list_repositories": {
        "description": "Use first when the repository id or generated alias is unknown.",
        "arguments": _LIST_REPOSITORIES_ARGUMENTS,
    },
    "codemesh_get_repository": {
        "description": "Fetch one indexed CodeMesh repository by id or alias.",
        "arguments": _GET_REPOSITORY_ARGUMENTS,
    },
    "codemesh_get_repository_status": {
        "description": "Use before trusting context to check counts, latest ingestion run, summary coverage, and local git freshness.",
        "arguments": _GET_REPOSITORY_STATUS_ARGUMENTS,
        "response": {
            "fields": [
                "repository_id",
                "repository",
                "latest_run",
                "summary_coverage",
                "counts",
                "freshness",
                "refresh",
                "generated_at",
            ],
        },
    },
    "codemesh_delete_repository": {
        "description": "Delete one indexed CodeMesh repository from graph, content, vectors, summaries, and registry data. Requires confirm=true.",
        "arguments": _DELETE_REPOSITORY_ARGUMENTS,
        "response": {
            "fields": [
                "repository_id",
                "deleted",
                "registry_entry_existed",
                "graph_cleaned",
                "content_cleaned",
                "embeddings_cleaned",
                "summaries_cleaned",
            ],
        },
    },
    "codemesh_get_summary_coverage": {
        "description": "Fetch generated node summary coverage for one indexed CodeMesh repository.",
        "arguments": _SUMMARY_COVERAGE_ARGUMENTS,
        "response": {
            "fields": [
                "repository_id",
                "total_count",
                "completed_count",
                "failed_count",
                "status_counts",
                "kind_counts",
                "provider_model_counts",
                "provider_model_count_details",
                "recent_failures",
                "generated_at",
            ],
        },
    },
    "codemesh_list_ingestion_runs": {
        "description": "List CodeMesh ingestion runs, optionally scoped to a repository id or alias.",
        "arguments": _LIST_RUNS_ARGUMENTS,
    },
}


def tool_manifest() -> dict[str, Any]:
    """Return the stable MCP tool contract used by tests and fallback output."""
    return {
        "service": "codemesh-agent-access",
        "protocol": "mcp",
        "tools": [
            {"name": name, "description": _TOOL_CONTRACTS[name]["description"]}
            for name in _TOOL_NAMES
        ],
        "contracts": deepcopy(_TOOL_CONTRACTS),
    }


def build_server(
    call_guard: Callable[[str, dict[str, Any]], None] | None = None,
) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The `mcp` package is required to run the CodeMesh MCP server."
        ) from exc

    server = FastMCP("codemesh-agent-access")

    def check(name: str, arguments: dict[str, Any]) -> None:
        if call_guard is not None:
            call_guard(name, arguments)

    @server.tool(description=_TOOL_CONTRACTS["codemesh_status"]["description"])
    async def codemesh_status() -> dict[str, Any]:
        """Return CodeMesh Agent Access health and configured read endpoints."""
        check("codemesh_status", {})
        return (await tools.status()).model_dump(mode="json")

    @server.tool(
        description=_TOOL_CONTRACTS["codemesh_get_tool_guidance"]["description"]
    )
    async def codemesh_get_tool_guidance(task: str | None = None) -> dict[str, Any]:
        """Recommend which CodeMesh MCP tools to use for a natural-language agent task."""
        check("codemesh_get_tool_guidance", {"task": task})
        return (await tools.tool_guidance(task=task)).model_dump(mode="json")

    @server.tool(description=_TOOL_CONTRACTS["codemesh_search_context"]["description"])
    async def codemesh_search_context(
        query: str,
        repository_id: str | None = None,
        limit: int = 8,
        kinds: list[str] | None = None,
        filters: dict[str, str] | None = None,
        vector: list[float] | None = None,
        expand_context: bool = True,
        context_depth: int = 4,
        include_context_relationships: bool = False,
        context_relationship_limit: int = 8,
    ) -> dict[str, Any]:
        """Search CodeMesh context for code relevant to an agent task."""
        check(
            "codemesh_search_context",
            {"query": query, "repository_id": repository_id, "limit": limit},
        )
        return (
            await tools.search_context(
                query,
                repository_id=repository_id,
                limit=limit,
                kinds=kinds,
                filters=filters,
                vector=vector,
                expand_context=expand_context,
                context_depth=context_depth,
                include_context_relationships=include_context_relationships,
                context_relationship_limit=context_relationship_limit,
            )
        ).model_dump(mode="json")

    @server.tool(
        description=_TOOL_CONTRACTS["codemesh_get_context_package"]["description"]
    )
    async def codemesh_get_context_package(
        query: str,
        repository_id: str | None = None,
        limit: int = 8,
        max_characters: int = 12000,
        kinds: list[str] | None = None,
        filters: dict[str, str] | None = None,
        vector: list[float] | None = None,
        context_depth: int = 4,
        include_content: bool = True,
        include_relationships: bool = True,
        relationship_limit: int = 8,
        caller_limit: int | None = None,
        callee_limit: int | None = None,
        read_limit: int | None = None,
        write_limit: int | None = None,
        contains_limit: int | None = None,
        definition_limit: int | None = None,
        uses_type_limit: int | None = None,
        include_repository: bool = True,
        output_format: Literal["json", "agent"] = "json",
    ) -> CallToolResult:
        """Build an agent-ready context package with snippets, relationships, and repository metadata."""
        check(
            "codemesh_get_context_package",
            {"query": query, "repository_id": repository_id, "limit": limit},
        )
        result = await tools.get_context_package(
            query,
            repository_id=repository_id,
            limit=limit,
            max_characters=max_characters,
            kinds=kinds,
            filters=filters,
            vector=vector,
            context_depth=context_depth,
            include_content=include_content,
            include_relationships=include_relationships,
            relationship_limit=relationship_limit,
            caller_limit=caller_limit,
            callee_limit=callee_limit,
            read_limit=read_limit,
            write_limit=write_limit,
            contains_limit=contains_limit,
            definition_limit=definition_limit,
            uses_type_limit=uses_type_limit,
            include_repository=include_repository,
        )
        if output_format == "agent":
            text = (
                format_context_package_for_agent(
                    result.data,
                    max_characters=min(max_characters, _MAX_MCP_AGENT_CHARACTERS),
                )
                if result.ok
                else result.error or "CodeMesh context package request failed."
            )
            return CallToolResult(
                content=[TextContent(type="text", text=text)],
                isError=not result.ok,
            )

        payload = result.model_dump(mode="json")
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload))],
            structuredContent=payload,
            isError=not result.ok,
        )

    @server.tool(description=_TOOL_CONTRACTS["codemesh_search_symbols"]["description"])
    async def codemesh_search_symbols(
        query: str,
        repository_id: str | None = None,
        limit: int = 20,
        kinds: list[str] | None = None,
        filters: dict[str, str] | None = None,
        include_declarations: bool = True,
    ) -> dict[str, Any]:
        """Search indexed CodeMesh symbols by name, id, display signature, namespace, or file path."""
        check(
            "codemesh_search_symbols",
            {"query": query, "repository_id": repository_id, "limit": limit},
        )
        return (
            await tools.search_symbols(
                query,
                repository_id=repository_id,
                limit=limit,
                kinds=kinds,
                filters=filters,
                include_declarations=include_declarations,
            )
        ).model_dump(mode="json")

    @server.tool(description=_TOOL_CONTRACTS["codemesh_get_node"]["description"])
    async def codemesh_get_node(
        node_id: str,
        repository_id: str | None = None,
        include_content: bool = True,
        include_neighbors: bool = True,
    ) -> dict[str, Any]:
        """Fetch a CodeMesh node with optional content and immediate relationships."""
        check(
            "codemesh_get_node",
            {"node_id": node_id, "repository_id": repository_id},
        )
        return (
            await tools.get_node(
                node_id,
                repository_id=repository_id,
                include_content=include_content,
                include_neighbors=include_neighbors,
            )
        ).model_dump(mode="json")

    @server.tool(description=_TOOL_CONTRACTS["codemesh_get_neighbors"]["description"])
    async def codemesh_get_neighbors(
        node_id: str,
        repository_id: str | None = None,
        depth: int = 1,
        relationship_kinds: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch relationships around a CodeMesh node."""
        check(
            "codemesh_get_neighbors",
            {"node_id": node_id, "repository_id": repository_id, "depth": depth},
        )
        return (
            await tools.get_neighbors(
                node_id,
                repository_id=repository_id,
                depth=depth,
                relationship_kinds=relationship_kinds,
            )
        ).model_dump(mode="json")

    @server.tool(
        description=_TOOL_CONTRACTS["codemesh_list_repositories"]["description"]
    )
    async def codemesh_list_repositories(limit: int = 50) -> dict[str, Any]:
        """List repositories indexed by CodeMesh."""
        check("codemesh_list_repositories", {"limit": limit})
        return (await tools.list_repositories(limit=limit)).model_dump(mode="json")

    @server.tool(description=_TOOL_CONTRACTS["codemesh_get_repository"]["description"])
    async def codemesh_get_repository(repository_id: str) -> dict[str, Any]:
        """Fetch one indexed CodeMesh repository by id."""
        check("codemesh_get_repository", {"repository_id": repository_id})
        return (await tools.get_repository(repository_id)).model_dump(mode="json")

    @server.tool(
        description=_TOOL_CONTRACTS["codemesh_get_repository_status"]["description"]
    )
    async def codemesh_get_repository_status(repository_id: str) -> dict[str, Any]:
        """Fetch repository status, counts, latest run, summary coverage, and freshness diagnostics."""
        check("codemesh_get_repository_status", {"repository_id": repository_id})
        return (await tools.get_repository_status(repository_id)).model_dump(
            mode="json"
        )

    @server.tool(
        description=_TOOL_CONTRACTS["codemesh_delete_repository"]["description"]
    )
    async def codemesh_delete_repository(
        repository_id: str, confirm: bool = False
    ) -> dict[str, Any]:
        """Delete one indexed CodeMesh repository. Requires confirm=true."""
        check(
            "codemesh_delete_repository",
            {"repository_id": repository_id, "confirm": confirm},
        )
        if not confirm:
            return {
                "ok": False,
                "data": {},
                "error": "Repository deletion requires confirm=true.",
            }

        return (await tools.delete_repository(repository_id)).model_dump(mode="json")

    @server.tool(
        description=_TOOL_CONTRACTS["codemesh_get_summary_coverage"]["description"]
    )
    async def codemesh_get_summary_coverage(repository_id: str) -> dict[str, Any]:
        """Fetch generated node summary coverage for one indexed CodeMesh repository."""
        check("codemesh_get_summary_coverage", {"repository_id": repository_id})
        return (await tools.get_summary_coverage(repository_id)).model_dump(mode="json")

    @server.tool(
        description=_TOOL_CONTRACTS["codemesh_list_ingestion_runs"]["description"]
    )
    async def codemesh_list_ingestion_runs(
        repository_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List CodeMesh ingestion runs, optionally scoped to a repository."""
        check(
            "codemesh_list_ingestion_runs",
            {"repository_id": repository_id, "limit": limit},
        )
        return (
            await tools.list_ingestion_runs(repository_id=repository_id, limit=limit)
        ).model_dump(mode="json")

    return server


def run() -> None:
    server = build_server()
    server.run()


async def print_tool_manifest() -> None:
    print(json.dumps(tool_manifest(), indent=2))


if __name__ == "__main__":
    try:
        run()
    except RuntimeError:
        asyncio.run(print_tool_manifest())
