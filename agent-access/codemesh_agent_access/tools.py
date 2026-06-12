from __future__ import annotations

from .dependencies import get_store
from .models import ContextPackageQuery, ContextQuery, NeighborQuery, NodeLookup, SymbolQuery, ToolResult
from .tool_guidance import get_tool_guidance


async def status() -> ToolResult:
    health = await get_store().health()
    return ToolResult(data=health.model_dump(mode="json"))


async def tool_guidance(task: str | None = None) -> ToolResult:
    return ToolResult(data=get_tool_guidance(task))


async def search_context(
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
) -> ToolResult:
    result = await get_store().search_context(
        ContextQuery(
            query=query,
            repository_id=repository_id,
            limit=limit,
            kinds=kinds or [],
            filters=filters or {},
            vector=vector or [],
            expand_context=expand_context,
            context_depth=context_depth,
            include_context_relationships=include_context_relationships,
            context_relationship_limit=context_relationship_limit,
        )
    )
    return ToolResult(data=result.model_dump(mode="json"))


async def get_context_package(
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
) -> ToolResult:
    result = await get_store().get_context_package(
        ContextPackageQuery(
            query=query,
            repository_id=repository_id,
            limit=limit,
            max_characters=max_characters,
            kinds=kinds or [],
            filters=filters or {},
            vector=vector or [],
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
    )
    return ToolResult(data=result.model_dump(mode="json"))


async def search_symbols(
    query: str,
    repository_id: str | None = None,
    limit: int = 20,
    kinds: list[str] | None = None,
    filters: dict[str, str] | None = None,
    include_declarations: bool = True,
) -> ToolResult:
    result = await get_store().search_symbols(
        SymbolQuery(
            query=query,
            repository_id=repository_id,
            limit=limit,
            kinds=kinds or [],
            filters=filters or {},
            include_declarations=include_declarations,
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


async def get_neighbors(
    node_id: str,
    repository_id: str | None = None,
    depth: int = 1,
    relationship_kinds: list[str] | None = None,
) -> ToolResult:
    result = await get_store().get_neighbors(
        NeighborQuery(
            node_id=node_id,
            repository_id=repository_id,
            depth=depth,
            relationship_kinds=relationship_kinds or [],
        )
    )
    return ToolResult(data=result.model_dump(mode="json"))


async def list_repositories(limit: int = 50) -> ToolResult:
    result = await get_store().list_repositories(limit=limit)
    return ToolResult(data=result.model_dump(mode="json"))


async def get_repository(repository_id: str) -> ToolResult:
    result = await get_store().get_repository(repository_id)
    return ToolResult(data={"repository": result.model_dump(mode="json") if result else None})


async def delete_repository(repository_id: str) -> ToolResult:
    result = await get_store().delete_repository(repository_id)
    return ToolResult(data=result.model_dump(mode="json"))


async def get_summary_coverage(repository_id: str) -> ToolResult:
    result = await get_store().get_summary_coverage(repository_id)
    return ToolResult(data=result.model_dump(mode="json"))


async def get_repository_status(repository_id: str) -> ToolResult:
    result = await get_store().get_repository_status(repository_id)
    return ToolResult(data=result.model_dump(mode="json"))


async def list_ingestion_runs(repository_id: str | None = None, limit: int = 50) -> ToolResult:
    result = await get_store().list_ingestion_runs(repository_id=repository_id, limit=limit)
    return ToolResult(data=result.model_dump(mode="json"))
