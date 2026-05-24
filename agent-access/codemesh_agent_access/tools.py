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
    expand_context: bool = True,
    context_depth: int = 4,
    include_context_relationships: bool = False,
    context_relationship_limit: int = 8,
) -> ToolResult:
    result = await get_store().search_context(
        ContextQuery(
            query=query,
            repository_id=repository_id,
            limit=limit,
            kinds=kinds or [],
            vector=vector or [],
            expand_context=expand_context,
            context_depth=context_depth,
            include_context_relationships=include_context_relationships,
            context_relationship_limit=context_relationship_limit,
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
