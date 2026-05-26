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


class ContextPackageQuery(BaseModel):
    query: str
    repository_id: str | None = None
    limit: int = 8
    max_characters: int = 12000
    kinds: list[str] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)
    vector: list[float] = Field(default_factory=list)
    context_depth: int = 4
    include_content: bool = True
    include_relationships: bool = True
    relationship_limit: int = 8
    caller_limit: int | None = None
    callee_limit: int | None = None
    read_limit: int | None = None
    write_limit: int | None = None
    contains_limit: int | None = None
    definition_limit: int | None = None
    uses_type_limit: int | None = None
    include_repository: bool = True


class ContextPackageItem(BaseModel):
    hit: ContextHit
    node: dict[str, Any] | None = None
    content: dict[str, Any] | None = None
    snippet: str | None = None
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    relationship_groups: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    rationale: dict[str, Any] = Field(default_factory=dict)


class ContextPackageResponse(BaseModel):
    query: ContextPackageQuery
    repository: dict[str, Any] | None = None
    latest_run: dict[str, Any] | None = None
    items: list[ContextPackageItem] = Field(default_factory=list)
    total_snippet_characters: int = 0
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


class RepositorySummary(BaseModel):
    repository_id: str
    alias: str | None = None
    root_path: str
    remote_url: str | None = None
    branch: str | None = None
    commit: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_run_id: str | None = None
    last_stage: str | None = None
    last_message: str | None = None
    node_count: int = 0
    relationship_count: int = 0
    content_count: int = 0
    embedding_count: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class RepositoryListResponse(BaseModel):
    repositories: list[RepositorySummary] = Field(default_factory=list)


class IngestionRunSummary(BaseModel):
    run_id: str
    repository_id: str
    repository_root: str
    stage: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None
    language: str
    parser_name: str
    solution_path: str | None = None
    project_path: str | None = None
    dry_run: bool = False
    skip_embeddings: bool = True
    embedding_provider: str
    embedding_model: str
    node_count: int = 0
    relationship_count: int = 0
    content_count: int = 0
    embedding_count: int = 0
    stats: dict[str, Any] | None = None
    diagnostic_count: int = 0
    error_diagnostic_count: int = 0
    warning_diagnostic_count: int = 0
    metadata: dict[str, str] = Field(default_factory=dict)


class IngestionRunListResponse(BaseModel):
    runs: list[IngestionRunSummary] = Field(default_factory=list)


class ToolResult(BaseModel):
    ok: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
