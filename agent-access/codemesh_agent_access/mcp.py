from __future__ import annotations

import asyncio
import json
from typing import Any

from . import tools


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

    return server


def run() -> None:
    server = build_server()
    server.run()


async def print_tool_manifest() -> None:
    manifest = {
        "service": "codemesh-agent-access",
        "tools": [
            "codemesh_status",
            "codemesh_search_context",
            "codemesh_get_node",
            "codemesh_get_neighbors",
        ],
    }
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    try:
        run()
    except RuntimeError:
        asyncio.run(print_tool_manifest())
