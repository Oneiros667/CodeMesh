from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from codemesh_agent_access.dependencies import get_store
from codemesh_agent_access.models import (
    ContextHit,
    ContextPackageItem,
    ContextPackageResponse,
    ContextQuery,
    ContextResponse,
    HealthResponse,
    IngestionRunListResponse,
    IngestionRunSummary,
    NeighborQuery,
    NodeLookup,
    NodeSummaryCoverageResponse,
    NodeResponse,
    RepositoryDeleteResponse,
    RepositoryListResponse,
    RepositorySummary,
    RepositoryStatusResponse,
    SymbolQuery,
    SymbolSearchHit,
    SymbolSearchResponse,
)
from codemesh_agent_access.rest import app


def test_rest_health_and_status_use_store_dependency() -> None:
    store = FakeRestStore()

    with rest_client(store) as client:
        health = client.get("/health")
        status = client.get("/status")

    assert health.status_code == 200
    assert status.status_code == 200
    assert health.json()["status"] == "healthy"
    assert status.json()["components"]["qdrant"]["status"] == "healthy"
    assert store.calls == ["health", "health"]


def test_rest_context_search_preserves_query_controls() -> None:
    store = FakeRestStore()

    with rest_client(store) as client:
        response = client.post(
            "/context/search",
            json={
                "query": "download",
                "repository_id": "sample_repo",
                "limit": 3,
                "kinds": ["Method"],
                "filters": {"project": "Sample"},
                "vector": [0.1, 0.2],
                "expand_context": False,
                "context_depth": 2,
                "include_context_relationships": True,
                "context_relationship_limit": 4,
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["query"]["repository_id"] == "sample_repo"
    assert payload["query"]["filters"] == {"project": "Sample"}
    assert payload["query"]["expand_context"] is False
    assert payload["diagnostics"] == {
        "mode": "vector",
        "embedding_source": "provided",
        "hit_count": 1,
    }
    assert payload["hits"][0]["node_id"] == "node:download"
    assert store.context_query is not None
    assert store.context_query.context_relationship_limit == 4


def test_rest_context_package_preserves_relationship_controls() -> None:
    store = FakeRestStore()

    with rest_client(store) as client:
        response = client.post(
            "/context/package",
            json={
                "query": "download",
                "repository_id": "repo:test",
                "limit": 2,
                "max_characters": 2000,
                "include_content": False,
                "include_relationships": True,
                "relationship_limit": 9,
                "caller_limit": 1,
                "callee_limit": 2,
                "read_limit": 0,
                "write_limit": 1,
                "include_repository": False,
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["query"]["include_repository"] is False
    assert payload["query"]["read_limit"] == 0
    assert payload["items"][0]["relationship_groups"]["callers"][0]["kind"] == "Invokes"
    assert store.package_query is not None
    assert store.package_query.max_characters == 2000


def test_rest_symbols_node_neighbors_and_registry_shapes() -> None:
    store = FakeRestStore()

    with rest_client(store) as client:
        symbols = client.post(
            "/symbols/search",
            json={
                "query": "DownloadAsync",
                "repository_id": "repo:test",
                "limit": 5,
                "kinds": ["Method"],
                "filters": {"project": "Sample"},
                "include_declarations": False,
            },
        )
        node = client.post(
            "/nodes/get",
            json={
                "node_id": "node:download",
                "repository_id": "repo:test",
                "include_content": False,
                "include_neighbors": True,
            },
        )
        neighbors = client.post(
            "/graph/neighbors",
            json={
                "node_id": "node:download",
                "repository_id": "repo:test",
                "depth": 2,
                "relationship_kinds": ["Invokes"],
            },
        )
        repositories = client.get("/repositories", params={"limit": 7})
        repository = client.get("/repositories/sample_repo")
        summary_coverage = client.get("/repositories/sample_repo/summaries")
        repository_status = client.get("/repositories/sample_repo/status")
        repository_with_path_chars = client.get("/repositories/sample%20repo%2Fid")
        delete_repository = client.delete("/repositories/sample_repo")
        runs = client.get("/ingestion-runs", params={"repository_id": "sample_repo", "limit": 2})

    assert symbols.status_code == 200
    assert symbols.json()["symbols"][0]["node"]["id"] == "node:download"
    assert store.symbol_query is not None
    assert store.symbol_query.include_declarations is False

    assert node.status_code == 200
    assert node.json()["node"]["id"] == "node:download"
    assert store.node_lookup is not None
    assert store.node_lookup.include_content is False

    assert neighbors.status_code == 200
    assert neighbors.json()["relationships"][0]["kind"] == "Invokes"
    assert store.neighbor_query is not None
    assert store.neighbor_query.relationship_kinds == ["Invokes"]

    assert repositories.status_code == 200
    assert repositories.json()["repositories"][0]["alias"] == "sample_repo"
    assert store.repository_limit == 7

    assert repository.status_code == 200
    assert repository.json()["repository_id"] == "repo:test"
    assert store.repository_ids[0] == "sample_repo"

    assert summary_coverage.status_code == 200
    assert summary_coverage.json()["completed_count"] == 3
    assert summary_coverage.json()["kind_counts"] == {"Method": 2, "Class": 1}
    assert store.summary_repository_ids == ["sample_repo"]

    assert repository_status.status_code == 200
    assert repository_status.json()["freshness"]["status"] == "unknown"
    assert repository_status.json()["counts"]["graph_nodes"] == 17
    assert store.status_repository_ids == ["sample_repo"]

    assert repository_with_path_chars.status_code == 200
    assert repository_with_path_chars.json()["repository_id"] == "repo:test"
    assert store.repository_ids[1] == "sample repo/id"

    assert delete_repository.status_code == 200
    assert delete_repository.json()["deleted"] is True
    assert store.deleted_repository_ids == ["sample_repo"]

    assert runs.status_code == 200
    assert runs.json()["runs"][0]["run_id"] == "run:test"
    assert store.runs_repository_id == "sample_repo"
    assert store.runs_limit == 2


def test_rest_ui_routes_render_existing_store_state() -> None:
    store = FakeRestStore()

    with rest_client(store) as client:
        dashboard = client.get("/ui")
        repositories = client.get("/ui/repositories")
        repository = client.get("/ui/repositories/sample_repo")
        runs = client.get("/ui/runs", params={"repository_id": "sample_repo"})
        search = client.get("/ui/search", params={"query": "download", "repository_id": "repo:test"})

    assert dashboard.status_code == 200
    assert "CodeMesh" in dashboard.text
    assert "Recent Ingestion Runs" in dashboard.text

    assert repositories.status_code == 200
    assert "sample_repo" in repositories.text
    assert "repo:test" in repositories.text

    assert repository.status_code == 200
    assert "Freshness" in repository.text
    assert "graph_nodes" in repository.text
    assert "run:test" in repository.text
    assert store.status_repository_ids == ["sample_repo"]

    assert runs.status_code == 200
    assert "run:test" in runs.text
    assert store.runs_repository_id == "sample_repo"

    assert search.status_code == 200
    assert "Downloader.cs:10-20" in search.text
    assert "node:download" in search.text
    assert store.context_query is not None
    assert store.context_query.expand_context is False
    assert store.context_query.repository_id == "repo:test"


def rest_client(store: "FakeRestStore") -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    return RestClient(app)


class RestClient(TestClient):
    def __exit__(self, *args: Any) -> bool | None:
        try:
            return super().__exit__(*args)
        finally:
            app.dependency_overrides.clear()


class FakeRestStore:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.context_query: ContextQuery | None = None
        self.package_query: Any = None
        self.symbol_query: SymbolQuery | None = None
        self.node_lookup: NodeLookup | None = None
        self.neighbor_query: NeighborQuery | None = None
        self.repository_limit: int | None = None
        self.repository_ids: list[str] = []
        self.deleted_repository_ids: list[str] = []
        self.summary_repository_ids: list[str] = []
        self.status_repository_ids: list[str] = []
        self.runs_repository_id: str | None = None
        self.runs_limit: int | None = None

    async def health(self) -> HealthResponse:
        self.calls.append("health")
        return HealthResponse(
            status="healthy",
            components={
                "qdrant": {"status": "healthy"},
                "neo4j": {"status": "healthy"},
            },
        )

    async def search_context(self, query: ContextQuery) -> ContextResponse:
        self.context_query = query
        return ContextResponse(
            query=query,
            hits=[
                ContextHit(
                    node_id="node:download",
                    stable_key="node:download",
                    kind="Method",
                    file_path="Downloader.cs",
                    start_line=10,
                    end_line=20,
                    score=0.9,
                    repository_id=query.repository_id,
                    content_hash="content:download",
                )
            ],
            diagnostics={
                "mode": "vector",
                "embedding_source": "provided",
                "hit_count": 1,
            },
        )

    async def get_context_package(self, query: Any) -> ContextPackageResponse:
        self.package_query = query
        hit = ContextHit(
            node_id="node:download",
            stable_key="node:download",
            kind="Method",
            file_path="Downloader.cs",
            start_line=10,
            end_line=20,
            score=0.9,
            repository_id=query.repository_id,
        )
        return ContextPackageResponse(
            query=query,
            items=[
                ContextPackageItem(
                    hit=hit,
                    node={"id": "node:download"},
                    relationships=[{"kind": "Invokes"}],
                    relationship_groups={"callers": [{"kind": "Invokes"}]},
                    rationale={"rank": 1},
                )
            ],
        )

    async def search_symbols(self, query: SymbolQuery) -> SymbolSearchResponse:
        self.symbol_query = query
        return SymbolSearchResponse(
            query=query,
            symbols=[
                SymbolSearchHit(
                    node={"id": "node:download", "kind": "Method"},
                    score=0.8,
                    score_components={"lexical_score": 0.8},
                )
            ],
        )

    async def get_node(self, lookup: NodeLookup) -> NodeResponse:
        self.node_lookup = lookup
        return NodeResponse(
            node={"id": lookup.node_id},
            relationships=[{"kind": "Invokes"}],
        )

    async def get_neighbors(self, query: NeighborQuery) -> NodeResponse:
        self.neighbor_query = query
        return NodeResponse(relationships=[{"kind": "Invokes"}])

    async def list_repositories(self, limit: int = 50) -> RepositoryListResponse:
        self.repository_limit = limit
        return RepositoryListResponse(
            repositories=[
                RepositorySummary(
                    repository_id="repo:test",
                    alias="sample_repo",
                    root_path="C:/sample",
                )
            ]
        )

    async def get_repository(self, repository_id: str) -> RepositorySummary | None:
        self.repository_ids.append(repository_id)
        return RepositorySummary(
            repository_id="repo:test",
            alias="sample_repo",
            root_path="C:/sample",
        )

    async def delete_repository(self, repository_id: str) -> RepositoryDeleteResponse:
        self.deleted_repository_ids.append(repository_id)
        return RepositoryDeleteResponse(
            repository_id="repo:test",
            deleted=True,
            registry_entry_existed=True,
            graph_cleaned=True,
            content_cleaned=True,
            embeddings_cleaned=True,
            summaries_cleaned=True,
        )

    async def get_summary_coverage(self, repository_id: str) -> NodeSummaryCoverageResponse:
        self.summary_repository_ids.append(repository_id)
        return NodeSummaryCoverageResponse(
            repository_id="repo:test",
            total_count=4,
            completed_count=3,
            failed_count=1,
            status_counts={"completed": 3, "failed": 1},
            kind_counts={"Method": 2, "Class": 1},
            provider_model_counts={"lmstudio/qwen/qwen2.5-coder-14b/node-summary-v1": 4},
            provider_model_count_details=[
                {
                    "provider": "lmstudio",
                    "model": "qwen/qwen2.5-coder-14b",
                    "prompt_version": "node-summary-v1",
                    "count": 4,
                }
            ],
            recent_failures=[{"node_id": "node:failed", "error": "model failed"}],
        )

    async def get_repository_status(self, repository_id: str) -> RepositoryStatusResponse:
        self.status_repository_ids.append(repository_id)
        return RepositoryStatusResponse(
            repository_id="repo:test",
            repository=RepositorySummary(
                repository_id="repo:test",
                alias="sample_repo",
                root_path="C:/sample",
                node_count=17,
                relationship_count=28,
                content_count=13,
                embedding_count=17,
            ),
            counts={"graph_nodes": 17, "relationships": 28, "content_documents": 13, "vectors": 17},
            freshness={"status": "unknown", "is_stale": None},
        )

    async def list_ingestion_runs(
        self,
        repository_id: str | None = None,
        limit: int = 50,
    ) -> IngestionRunListResponse:
        self.runs_repository_id = repository_id
        self.runs_limit = limit
        return IngestionRunListResponse(
            runs=[
                IngestionRunSummary(
                    run_id="run:test",
                    repository_id="repo:test",
                    repository_root="C:/sample",
                    stage="Completed",
                    language="csharp",
                    parser_name="test",
                    embedding_provider="lmstudio",
                    embedding_model="text-embedding-nomic-embed-text-v2-moe",
                )
            ]
        )
