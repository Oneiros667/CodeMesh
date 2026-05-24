from __future__ import annotations

from .dependencies import get_store
from .models import ContextQuery, NeighborQuery, NodeLookup, ToolResult


async def status() -> ToolResult:
    health = await get_store().health()
    return ToolResult(data=health.model_dump(mode="json"))


async def search_context(
    query: str,
    repository_id: str | None = None,
    limit: int = 8,
    kinds: list[str] | None = None,
    vector: list[float] | None = None,
) -> ToolResult:
    result = await get_store().search_context(
        ContextQuery(
            query=query,
            repository_id=repository_id,
            limit=limit,
            kinds=kinds or [],
            vector=vector or [],
        )
    )
    return ToolResult(data=result.model_dump(mode="json"))


async def get_node(
    node_id: str,
    repository_id: str | None = None,
    include_content: bool = True,
    include_neighbors: bool = True,
) -> ToolResult:
    result = await get_store().get_node(
        NodeLookup(
            node_id=node_id,
            repository_id=repository_id,
            include_content=include_content,
            include_neighbors=include_neighbors,
        )
    )
    return ToolResult(data=result.model_dump(mode="json"))


async def get_neighbors(node_id: str, repository_id: str | None = None, depth: int = 1) -> ToolResult:
    result = await get_store().get_neighbors(
        NeighborQuery(node_id=node_id, repository_id=repository_id, depth=depth)
    )
    return ToolResult(data=result.model_dump(mode="json"))
