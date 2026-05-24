from __future__ import annotations

from fastapi import Depends, FastAPI

from .models import ContextQuery, ContextResponse, HealthResponse, NeighborQuery, NodeLookup, NodeResponse
from .store import CodeMeshReadStore
from .dependencies import get_store

app = FastAPI(
    title="CodeMesh Agent Access",
    version="0.1.0",
    description="REST API for AI agents to read CodeMesh graph, content, and vector intelligence.",
)


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
