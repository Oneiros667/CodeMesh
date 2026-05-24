from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    service: str = "codemesh-agent-access"
    status: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    components: dict[str, Any] = Field(default_factory=dict)


class ContextQuery(BaseModel):
    query: str
    repository_id: str | None = None
    limit: int = 8
    kinds: list[str] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)
    vector: list[float] = Field(default_factory=list)
    expand_context: bool = True
    context_depth: int = 4
    include_context_relationships: bool = False
    context_relationship_limit: int = 8


class ContextHit(BaseModel):
    node_id: str
    stable_key: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    score: float
    repository_id: str | None = None
    content_hash: str | None = None
    score_components: dict[str, float] = Field(default_factory=dict)
    expanded_context: dict[str, Any] | None = None
    preview: str | None = None


class ContextResponse(BaseModel):
    query: ContextQuery
    hits: list[ContextHit] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NodeLookup(BaseModel):
    node_id: str
    repository_id: str | None = None
    include_content: bool = True
    include_neighbors: bool = True


class NodeResponse(BaseModel):
    node: dict[str, Any] | None = None
    content: dict[str, Any] | None = None
    relationships: list[dict[str, Any]] = Field(default_factory=list)


class NeighborQuery(BaseModel):
    node_id: str
    repository_id: str | None = None
    depth: int = 1
    relationship_kinds: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    ok: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
