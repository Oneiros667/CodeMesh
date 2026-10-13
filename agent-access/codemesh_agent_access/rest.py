from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI

from . import __version__
from .models import (
    ContextQuery,
    ContextResponse,
    ContextPackageQuery,
    ContextPackageResponse,
    HealthResponse,
    IngestionRunListResponse,
    NeighborQuery,
    NodeLookup,
    NodeSummaryCoverageResponse,
    NodeResponse,
    RepositoryDeleteResponse,
    RepositoryListResponse,
    RepositorySummary,
    RepositoryStatusResponse,
    SymbolQuery,
    SymbolSearchResponse,
)
from .store import CodeMeshReadStore
from .dependencies import close_store, get_store
from .web import router as web_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await close_store()


app = FastAPI(
    title="CodeMesh Agent Access",
    version=__version__,
    description="REST API for AI agents to read CodeMesh graph, content, and vector intelligence.",
    lifespan=lifespan,
)
app.include_router(web_router)


@app.get("/health", response_model=HealthResponse)
async def health(store: CodeMeshReadStore = Depends(get_store)) -> HealthResponse:
    return await store.health()


@app.get("/status", response_model=HealthResponse)
async def status(store: CodeMeshReadStore = Depends(get_store)) -> HealthResponse:
    return await store.health()


@app.post("/context/search", response_model=ContextResponse)
async def search_context(
    query: ContextQuery,
    store: CodeMeshReadStore = Depends(get_store),
) -> ContextResponse:
    return await store.search_context(query)


@app.post("/context/package", response_model=ContextPackageResponse)
async def get_context_package(
    query: ContextPackageQuery,
    store: CodeMeshReadStore = Depends(get_store),
) -> ContextPackageResponse:
    return await store.get_context_package(query)


@app.post("/symbols/search", response_model=SymbolSearchResponse)
async def search_symbols(
    query: SymbolQuery,
    store: CodeMeshReadStore = Depends(get_store),
) -> SymbolSearchResponse:
    return await store.search_symbols(query)


@app.post("/nodes/get", response_model=NodeResponse)
async def get_node(
    lookup: NodeLookup,
    store: CodeMeshReadStore = Depends(get_store),
) -> NodeResponse:
    return await store.get_node(lookup)


@app.post("/graph/neighbors", response_model=NodeResponse)
async def get_neighbors(
    query: NeighborQuery,
    store: CodeMeshReadStore = Depends(get_store),
) -> NodeResponse:
    return await store.get_neighbors(query)


@app.get("/repositories", response_model=RepositoryListResponse)
async def list_repositories(
    limit: int = 50,
    store: CodeMeshReadStore = Depends(get_store),
) -> RepositoryListResponse:
    return await store.list_repositories(limit=limit)


@app.get(
    "/repositories/{repository_id}/summaries",
    response_model=NodeSummaryCoverageResponse,
)
async def get_repository_summary_coverage(
    repository_id: str,
    store: CodeMeshReadStore = Depends(get_store),
) -> NodeSummaryCoverageResponse:
    return await store.get_summary_coverage(repository_id)


@app.get(
    "/repositories/{repository_id}/status", response_model=RepositoryStatusResponse
)
async def get_repository_status(
    repository_id: str,
    store: CodeMeshReadStore = Depends(get_store),
) -> RepositoryStatusResponse:
    return await store.get_repository_status(repository_id)


@app.get("/repositories/{repository_id:path}", response_model=RepositorySummary | None)
async def get_repository(
    repository_id: str,
    store: CodeMeshReadStore = Depends(get_store),
) -> RepositorySummary | None:
    return await store.get_repository(repository_id)


@app.delete(
    "/repositories/{repository_id:path}", response_model=RepositoryDeleteResponse
)
async def delete_repository(
    repository_id: str,
    store: CodeMeshReadStore = Depends(get_store),
) -> RepositoryDeleteResponse:
    return await store.delete_repository(repository_id)


@app.get("/ingestion-runs", response_model=IngestionRunListResponse)
async def list_ingestion_runs(
    repository_id: str | None = None,
    limit: int = 50,
    store: CodeMeshReadStore = Depends(get_store),
) -> IngestionRunListResponse:
    return await store.list_ingestion_runs(repository_id=repository_id, limit=limit)
