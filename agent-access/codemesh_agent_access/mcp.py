from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from typing import Any, Callable, Literal

from mcp.types import CallToolResult, TextContent

from . import tools
from .binding import RepositoryBinding, bound_repository_reference
from .formatting import format_context_package_for_agent


DEFAULT_TOOL_PROFILE = "normal"

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
    "codemesh_get_summary_coverage",
    "codemesh_list_ingestion_runs",
]

_NORMAL_TOOL_NAMES = [
    "codemesh_get_context_package",
    "codemesh_get_repository_status",
    "codemesh_list_repositories",
    "codemesh_get_node",
]

_TOOL_PROFILES = {
    DEFAULT_TOOL_PROFILE: _NORMAL_TOOL_NAMES,
    "diagnostic": _TOOL_NAMES,
}

_MAX_MCP_AGENT_CHARACTERS = 12000

_SERVER_INSTRUCTIONS = (
    "Use CodeMesh first for source-grounded implementation discovery, likely "
    "change-impact analysis, and validation selection in indexed repositories. "
    "Start with codemesh_get_context_package using the full task, the repository "
    "id or alias, output_format='agent', and default limits. Use the returned "
    "ranked file spans for targeted, batched checkout reads needed to verify "
    "citations instead of repeating broad repository exploration. If the "
    "repository is unknown, call codemesh_list_repositories; before trusting "
    "context, call codemesh_get_repository_status to confirm freshness."
)

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
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias; omit when the server is checkout-bound.",
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
        "description": "Use before trusting context to check counts, latest ingestion run, summary coverage, and local git freshness. Follow codemesh_next_action in the result: a fresh accepted binding continues immediately to codemesh_get_context_package; any other state stops CodeMesh use.",
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
                "codemesh_next_action",
                "generated_at",
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


def tool_profile_names() -> tuple[str, ...]:
    return tuple(_TOOL_PROFILES)


def _tool_names_for_profile(profile: str) -> list[str]:
    try:
        return _TOOL_PROFILES[profile]
    except KeyError as exc:
        supported = ", ".join(tool_profile_names())
        raise ValueError(
            f"Unknown MCP tool profile '{profile}'. Expected one of: {supported}."
        ) from exc


def _filter_tool_guidance(
    payload: dict[str, Any], tool_names: set[str]
) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return payload

    data["available_tools"] = [
        name for name in data.get("available_tools", []) if name in tool_names
    ]
    data["default_start"] = [
        name for name in data.get("default_start", []) if name in tool_names
    ]
    data["recommended_workflows"] = [
        workflow
        for workflow in data.get("recommended_workflows", [])
        if all(step.get("tool") in tool_names for step in workflow.get("steps", []))
    ]
    return payload


def _server_instructions(binding: RepositoryBinding | None) -> str:
    if binding is None:
        return _SERVER_INSTRUCTIONS
    return (
        f"{_SERVER_INSTRUCTIONS} This server is bound to project "
        f"'{binding.project_id}', checkout '{binding.checkout_id}', and repository "
        f"root '{binding.repository_root}'. Repository-scoped calls default to this "
        "binding and cannot override it."
    )


def tool_manifest(
    profile: str = DEFAULT_TOOL_PROFILE,
    binding: RepositoryBinding | None = None,
) -> dict[str, Any]:
    """Return the stable MCP tool contract used by tests and fallback output."""
    tool_names = _tool_names_for_profile(profile)
    return {
        "service": "codemesh-agent-access",
        "protocol": "mcp",
        "profile": profile,
        "instructions": _server_instructions(binding),
        "tools": [
            {"name": name, "description": _TOOL_CONTRACTS[name]["description"]}
            for name in tool_names
        ],
        "contracts": {name: deepcopy(_TOOL_CONTRACTS[name]) for name in tool_names},
        "binding": binding.as_dict() if binding is not None else None,
    }


def build_server(
    profile: str = DEFAULT_TOOL_PROFILE,
    call_guard: Callable[[str, dict[str, Any]], None] | None = None,
    binding: RepositoryBinding | None = None,
) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The `mcp` package is required to run the CodeMesh MCP server."
        ) from exc

    tool_names = set(_tool_names_for_profile(profile))
    server = FastMCP(
        "codemesh-agent-access",
        instructions=_server_instructions(binding),
    )

    def register_tool(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def register(function: Callable[..., Any]) -> Callable[..., Any]:
            if name not in tool_names:
                return function
            return server.tool(description=_TOOL_CONTRACTS[name]["description"])(
                function
            )

        return register

    def check(name: str, arguments: dict[str, Any]) -> None:
        if call_guard is not None:
            call_guard(name, arguments)

    def repository_reference(
        repository_id: str | None,
        *,
        required_when_unbound: bool = False,
    ) -> str | None:
        return bound_repository_reference(
            binding,
            repository_id,
            required_when_unbound=required_when_unbound,
        )

    @register_tool("codemesh_status")
    async def codemesh_status() -> dict[str, Any]:
        """Return CodeMesh Agent Access health and configured read endpoints."""
        check("codemesh_status", {})
        return (await tools.status()).model_dump(mode="json")

    @register_tool("codemesh_get_tool_guidance")
    async def codemesh_get_tool_guidance(task: str | None = None) -> dict[str, Any]:
        """Recommend which CodeMesh MCP tools to use for a natural-language agent task."""
        check("codemesh_get_tool_guidance", {"task": task})
        payload = (await tools.tool_guidance(task=task)).model_dump(mode="json")
        return _filter_tool_guidance(payload, tool_names)

    @register_tool("codemesh_search_context")
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
        repository_id = repository_reference(repository_id)
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

    @register_tool("codemesh_get_context_package")
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
        repository_id = repository_reference(
            repository_id,
            required_when_unbound=profile == DEFAULT_TOOL_PROFILE,
        )
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
            binding=binding,
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

    @register_tool("codemesh_search_symbols")
    async def codemesh_search_symbols(
        query: str,
        repository_id: str | None = None,
        limit: int = 20,
        kinds: list[str] | None = None,
        filters: dict[str, str] | None = None,
        include_declarations: bool = True,
    ) -> dict[str, Any]:
        """Search indexed CodeMesh symbols by name, id, display signature, namespace, or file path."""
        repository_id = repository_reference(repository_id)
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

    @register_tool("codemesh_get_node")
    async def codemesh_get_node(
        node_id: str,
        repository_id: str | None = None,
        include_content: bool = True,
        include_neighbors: bool = True,
    ) -> dict[str, Any]:
        """Fetch a CodeMesh node with optional content and immediate relationships."""
        repository_id = repository_reference(
            repository_id,
            required_when_unbound=profile == DEFAULT_TOOL_PROFILE,
        )
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
                binding=binding,
            )
        ).model_dump(mode="json")

    @register_tool("codemesh_get_neighbors")
    async def codemesh_get_neighbors(
        node_id: str,
        repository_id: str | None = None,
        depth: int = 1,
        relationship_kinds: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch relationships around a CodeMesh node."""
        repository_id = repository_reference(repository_id)
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

    @register_tool("codemesh_list_repositories")
    async def codemesh_list_repositories(limit: int = 50) -> dict[str, Any]:
        """List repositories indexed by CodeMesh."""
        check("codemesh_list_repositories", {"limit": limit})
        return (await tools.list_repositories(limit=limit, binding=binding)).model_dump(
            mode="json"
        )

    @register_tool("codemesh_get_repository")
    async def codemesh_get_repository(repository_id: str) -> dict[str, Any]:
        """Fetch one indexed CodeMesh repository by id."""
        repository_id = repository_reference(
            repository_id,
            required_when_unbound=True,
        )
        assert repository_id is not None
        check("codemesh_get_repository", {"repository_id": repository_id})
        return (await tools.get_repository(repository_id)).model_dump(mode="json")

    @register_tool("codemesh_get_repository_status")
    async def codemesh_get_repository_status(
        repository_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch repository status, counts, latest run, summary coverage, and freshness diagnostics."""
        repository_id = repository_reference(
            repository_id,
            required_when_unbound=True,
        )
        assert repository_id is not None
        check("codemesh_get_repository_status", {"repository_id": repository_id})
        payload = (
            await tools.get_repository_status(repository_id, binding=binding)
        ).model_dump(mode="json")
        status = payload.get("data")
        status = status if isinstance(status, dict) else {}
        status["codemesh_next_action"] = _repository_status_next_action(status)
        return payload

    @register_tool("codemesh_get_summary_coverage")
    async def codemesh_get_summary_coverage(repository_id: str) -> dict[str, Any]:
        """Fetch generated node summary coverage for one indexed CodeMesh repository."""
        repository_id = repository_reference(
            repository_id,
            required_when_unbound=True,
        )
        assert repository_id is not None
        check("codemesh_get_summary_coverage", {"repository_id": repository_id})
        return (await tools.get_summary_coverage(repository_id)).model_dump(mode="json")

    @register_tool("codemesh_list_ingestion_runs")
    async def codemesh_list_ingestion_runs(
        repository_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List CodeMesh ingestion runs, optionally scoped to a repository."""
        repository_id = repository_reference(repository_id)
        check(
            "codemesh_list_ingestion_runs",
            {"repository_id": repository_id, "limit": limit},
        )
        return (
            await tools.list_ingestion_runs(repository_id=repository_id, limit=limit)
        ).model_dump(mode="json")

    return server


def _repository_status_next_action(payload: dict[str, Any]) -> dict[str, Any]:
    freshness = payload.get("freshness")
    freshness = freshness if isinstance(freshness, dict) else {}
    binding = freshness.get("binding")
    binding = binding if isinstance(binding, dict) else {}
    eligible = (
        freshness.get("status") == "fresh" and binding.get("status") == "accepted"
    )
    if eligible:
        return {
            "use_codemesh": True,
            "next_tool": "codemesh_get_context_package",
            "instruction": (
                "Binding is accepted and the index is fresh. Continue now with "
                "codemesh_get_context_package using the full task as query and "
                "output_format='agent'; do not stop CodeMesh discovery after "
                "this status check."
            ),
        }

    return {
        "use_codemesh": False,
        "next_tool": None,
        "instruction": (
            "Do not use CodeMesh context for this task because the exact binding "
            "is not both accepted and fresh. Fall back to direct source inspection."
        ),
    }


def run(
    profile: str = DEFAULT_TOOL_PROFILE,
    binding: RepositoryBinding | None = None,
) -> None:
    if profile == DEFAULT_TOOL_PROFILE and binding is None:
        raise ValueError(
            "The normal MCP profile requires an explicit project, checkout, and "
            "repository-root binding."
        )
    server = build_server(profile=profile, binding=binding)
    server.run()


async def print_tool_manifest(profile: str = DEFAULT_TOOL_PROFILE) -> None:
    print(json.dumps(tool_manifest(profile=profile), indent=2))


if __name__ == "__main__":
    try:
        run()
    except RuntimeError:
        asyncio.run(print_tool_manifest())
