from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from typing import Any

from . import tools


_TOOL_NAMES = [
    "codemesh_status",
    "codemesh_search_context",
    "codemesh_get_context_package",
    "codemesh_get_node",
    "codemesh_get_neighbors",
    "codemesh_list_repositories",
    "codemesh_get_repository",
    "codemesh_list_ingestion_runs",
]

_CONTEXT_PACKAGE_ARGUMENTS: dict[str, dict[str, Any]] = {
    "query": {"type": "string", "required": True},
    "repository_id": {"type": "string|null", "default": None},
    "limit": {"type": "integer", "default": 8},
    "max_characters": {"type": "integer", "default": 12000},
    "kinds": {"type": "string[]|null", "default": None},
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


def tool_manifest() -> dict[str, Any]:
    """Return the stable MCP tool contract used by tests and fallback output."""
    return {
        "service": "codemesh-agent-access",
        "protocol": "mcp",
        "tools": [{"name": name} for name in _TOOL_NAMES],
        "contracts": {
            "codemesh_get_context_package": {
                "description": "Build an agent-ready context package with snippets, relationships, and repository metadata.",
                "arguments": deepcopy(_CONTEXT_PACKAGE_ARGUMENTS),
                "response": {
                    "relationship_groups": list(_RELATIONSHIP_GROUPS),
                },
            },
        },
    }


def build_server() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("The `mcp` package is required to run the CodeMesh MCP server.") from exc

    server = FastMCP("codemesh-agent-access")

    @server.tool()
    async def codemesh_status() -> dict[str, Any]:
        """Return CodeMesh Agent Access health and configured read endpoints."""
        return (await tools.status()).model_dump(mode="json")

    @server.tool()
    async def codemesh_search_context(
        query: str,
        repository_id: str | None = None,
        limit: int = 8,
        kinds: list[str] | None = None,
        vector: list[float] | None = None,
        expand_context: bool = True,
        context_depth: int = 4,
        include_context_relationships: bool = False,
        context_relationship_limit: int = 8,
    ) -> dict[str, Any]:
        """Search CodeMesh context for code relevant to an agent task."""
        return (
            await tools.search_context(
                query,
                repository_id=repository_id,
                limit=limit,
                kinds=kinds,
                vector=vector,
                expand_context=expand_context,
                context_depth=context_depth,
                include_context_relationships=include_context_relationships,
                context_relationship_limit=context_relationship_limit,
            )
        ).model_dump(mode="json")

    @server.tool()
    async def codemesh_get_context_package(
        query: str,
        repository_id: str | None = None,
        limit: int = 8,
        max_characters: int = 12000,
        kinds: list[str] | None = None,
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
    ) -> dict[str, Any]:
        """Build an agent-ready context package with snippets, relationships, and repository metadata."""
        return (
            await tools.get_context_package(
                query,
                repository_id=repository_id,
                limit=limit,
                max_characters=max_characters,
                kinds=kinds,
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
            )
        ).model_dump(mode="json")

    @server.tool()
    async def codemesh_get_node(
        node_id: str,
        repository_id: str | None = None,
        include_content: bool = True,
        include_neighbors: bool = True,
    ) -> dict[str, Any]:
        """Fetch a CodeMesh node with optional content and immediate relationships."""
        return (
            await tools.get_node(
                node_id,
                repository_id=repository_id,
                include_content=include_content,
                include_neighbors=include_neighbors,
            )
        ).model_dump(mode="json")

    @server.tool()
    async def codemesh_get_neighbors(
        node_id: str,
        repository_id: str | None = None,
        depth: int = 1,
    ) -> dict[str, Any]:
        """Fetch relationships around a CodeMesh node."""
        return (await tools.get_neighbors(node_id, repository_id=repository_id, depth=depth)).model_dump(mode="json")

    @server.tool()
    async def codemesh_list_repositories(limit: int = 50) -> dict[str, Any]:
        """List repositories indexed by CodeMesh."""
        return (await tools.list_repositories(limit=limit)).model_dump(mode="json")

    @server.tool()
    async def codemesh_get_repository(repository_id: str) -> dict[str, Any]:
        """Fetch one indexed CodeMesh repository by id."""
        return (await tools.get_repository(repository_id)).model_dump(mode="json")

    @server.tool()
    async def codemesh_list_ingestion_runs(
        repository_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List CodeMesh ingestion runs, optionally scoped to a repository."""
        return (await tools.list_ingestion_runs(repository_id=repository_id, limit=limit)).model_dump(mode="json")

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
