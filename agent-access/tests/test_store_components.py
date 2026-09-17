from __future__ import annotations

import asyncio
from typing import Any

import pytest

from codemesh_agent_access import embeddings as embeddings_module
from codemesh_agent_access.binding import (
    RepositoryBinding,
    RepositoryBindingError,
    assess_binding,
)
from codemesh_agent_access.content_store import (
    MongoContentStore,
    bound_repository_document,
    normalize_ingestion_run,
    normalize_repository,
    repository_alias,
)
from codemesh_agent_access.config import Settings
from codemesh_agent_access.embeddings import (
    QueryEmbeddingProvider,
    _listed_model_ids,
    model_provider,
)
from codemesh_agent_access.graph_store import (
    Neo4jGraphStore,
    lexical_terms,
    storage_key,
)
from codemesh_agent_access.models import (
    ContextPackageQuery,
    IngestionRunSummary,
    RepositoryStatusResponse,
    RepositorySummary,
)
from codemesh_agent_access.store import CodeMeshReadStore, _refresh_status
from codemesh_agent_access.summary_store import (
    MongoNodeSummaryStore,
    normalize_node_summary,
)
from codemesh_agent_access.vector_store import qdrant_filter_for


def test_model_provider_normalizes_lm_studio_aliases() -> None:
    assert model_provider("lmstudio") == "lmstudio"
    assert model_provider("LM-Studio") == "lmstudio"
    assert model_provider("lm_studio") == "lmstudio"
    assert model_provider(" ollama ") == "ollama"


def test_settings_uses_provider_default_when_embedding_model_is_blank(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CODEMESH_MODEL_PROVIDER", "lmstudio")
    monkeypatch.setenv("CODEMESH_EMBEDDING_MODEL", "")

    settings = Settings.from_env()

    assert settings.embedding_model == "text-embedding-nomic-embed-text-v2-moe"
    assert settings.mongo_node_summaries_collection == "node_summaries"


def test_model_list_parsing_supports_ollama_and_lm_studio_shapes() -> None:
    assert _listed_model_ids(
        "ollama",
        {"models": [{"name": "nomic-embed-text-v2-moe:latest"}, {"model": "other"}]},
    ) == {"nomic-embed-text-v2-moe:latest", "other"}
    assert _listed_model_ids(
        "lmstudio",
        {"data": [{"id": "text-embedding-nomic-embed-text-v2-moe"}]},
    ) == {"text-embedding-nomic-embed-text-v2-moe"}


def test_query_embedding_health_degrades_when_configured_model_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CODEMESH_MODEL_PROVIDER", "lmstudio")
    monkeypatch.setenv("CODEMESH_EMBEDDING_MODEL", "expected-model")
    monkeypatch.setattr(embeddings_module.httpx, "AsyncClient", FakeAsyncClient)

    FakeAsyncClient.payload = {"data": [{"id": "expected-model"}]}
    healthy = asyncio.run(QueryEmbeddingProvider(Settings.from_env()).health())
    assert healthy["status"] == "healthy"

    FakeAsyncClient.payload = {"data": [{"id": "other-model"}]}
    degraded = asyncio.run(QueryEmbeddingProvider(Settings.from_env()).health())
    assert degraded["status"] == "degraded"
    assert (
        degraded["detail"]
        == "Configured embedding model is not listed by the model provider."
    )


def test_query_embedding_provider_prefixes_queries(monkeypatch) -> None:
    monkeypatch.setenv("CODEMESH_MODEL_PROVIDER", "lmstudio")
    monkeypatch.setenv("CODEMESH_EMBEDDING_MODEL", "expected-model")
    monkeypatch.setattr(embeddings_module.httpx, "AsyncClient", FakeAsyncClient)
    FakeAsyncClient.payload = {"data": [{"index": 0, "embedding": [0.25, 0.5]}]}
    FakeAsyncClient.last_json = None

    embedding = asyncio.run(
        QueryEmbeddingProvider(Settings.from_env()).embed_query("find greeting")
    )

    assert embedding == [0.25, 0.5]
    assert FakeAsyncClient.last_json == {
        "model": "expected-model",
        "input": ["search_query: find greeting"],
    }


def test_qdrant_filter_maps_exact_payload_matches() -> None:
    assert qdrant_filter_for({}) is None
    assert qdrant_filter_for({"repositoryId": "repo:test", "kind": "Method"}) == {
        "must": [
            {"key": "repositoryId", "match": {"value": "repo:test"}},
            {"key": "kind", "match": {"value": "Method"}},
        ]
    }


def test_repository_alias_splits_paths_and_camel_case() -> None:
    assert (
        repository_alias("/fixtures/YoutubeDownloader") == "fixtures_youtube_downloader"
    )
    assert repository_alias("YoutubeDownloader") == "youtube_downloader"
    assert repository_alias("") == "repository"


def test_content_store_normalizers_preserve_registry_fields() -> None:
    repository = normalize_repository(
        {
            "_id": "repo:test",
            "alias": "sample_repo",
            "rootPath": "C:/sample",
            "nodeCount": "4",
            "relationshipCount": 3,
            "contentCount": None,
            "embeddingCount": "2",
            "metadata": {"language": "csharp"},
        }
    )

    assert repository.repository_id == "repo:test"
    assert repository.alias == "sample_repo"
    assert repository.node_count == 4
    assert repository.relationship_count == 3
    assert repository.content_count == 0
    assert repository.embedding_count == 2
    assert repository.metadata == {"language": "csharp"}

    run = normalize_ingestion_run(
        {
            "_id": "run:test",
            "repositoryId": "repo:test",
            "skipEmbeddings": False,
            "stats": {
                "ParsedNodeCount": "7",
                "writtenEmbeddingCount": "5",
                "SummaryCandidateCount": "4",
                "writtenSummaryCount": "2",
                "skippedSummaryCount": "1",
                "failedSummaryCount": "1",
            },
        }
    )

    assert run.run_id == "run:test"
    assert run.repository_id == "repo:test"
    assert run.skip_embeddings is False
    assert run.stats == {
        "parsed_node_count": 7,
        "written_node_count": 0,
        "skipped_node_count": 0,
        "parsed_relationship_count": 0,
        "written_relationship_count": 0,
        "skipped_relationship_count": 0,
        "parsed_content_count": 0,
        "written_content_count": 0,
        "skipped_content_count": 0,
        "written_embedding_count": 5,
        "skipped_embedding_count": 0,
        "summary_candidate_count": 4,
        "written_summary_count": 2,
        "skipped_summary_count": 1,
        "failed_summary_count": 1,
    }


def test_bound_repository_document_uses_exact_checkout_slot() -> None:
    document = bound_repository_document(
        {
            "_id": "project:test",
            "alias": "sample_repo",
            "rootPath": "/wrong/last-writer",
            "metadata": {"language": "python"},
        },
        {
            "_id": "checkout:secondary",
            "projectId": "project:test",
            "rootPath": "/work/secondary",
            "lastSeenAtUtc": "2026-08-31T00:00:00Z",
        },
        {
            "kind": "CheckoutCurrent",
            "key": "checkout:secondary",
            "snapshotId": "snapshot:secondary",
        },
        {
            "_id": "snapshot:secondary",
            "projectId": "project:test",
            "sourceViewHash": "view:secondary",
            "nodeCount": 7,
            "relationshipCount": 5,
            "contentCount": 3,
        },
        {
            "branch": "feature/secondary",
            "commit": "abc123",
            "workingTreeDirty": False,
        },
    )
    repository = normalize_repository(document)

    assert repository.project_id == "project:test"
    assert repository.checkout_id == "checkout:secondary"
    assert repository.snapshot_id == "snapshot:secondary"
    assert repository.root_path == "/work/secondary"
    assert repository.commit == "abc123"
    assert repository.source_view_hash == "view:secondary"
    assert repository.metadata["workingTreeDirty"] == "false"
    assert repository.node_count == 7


def test_binding_assessment_requires_exact_identity_root_and_freshness(
    tmp_path,
) -> None:
    binding = RepositoryBinding(
        "project:test",
        "checkout:test",
        str(tmp_path),
        "view:test",
    )
    repository = RepositorySummary(
        repository_id="project:test",
        project_id="project:test",
        checkout_id="checkout:test",
        snapshot_id="snapshot:test",
        source_view_hash="view:test",
        root_path=str(tmp_path),
    )

    accepted = assess_binding(
        binding,
        repository,
        {"status": "fresh", "is_stale": False, "provenance_status": "known"},
    )
    rejected = assess_binding(
        binding,
        repository.model_copy(update={"checkout_id": "checkout:other"}),
        {"status": "stale", "is_stale": True, "provenance_status": "known"},
    )

    assert accepted["status"] == "accepted"
    assert accepted["issues"] == []
    assert rejected["status"] == "rejected"
    assert rejected["issues"] == ["checkout_mismatch", "snapshot_not_fresh"]


def test_context_package_rejects_unaccepted_binding_before_search(tmp_path) -> None:
    store = object.__new__(CodeMeshReadStore)
    binding = RepositoryBinding("project:test", "checkout:test", str(tmp_path))

    async def fake_status(*args: Any, **kwargs: Any) -> RepositoryStatusResponse:
        return RepositoryStatusResponse(
            repository_id="project:test",
            freshness={
                "status": "stale",
                "is_stale": True,
                "binding": {
                    "status": "rejected",
                    "issues": ["snapshot_not_fresh"],
                },
            },
        )

    store.get_repository_status = fake_status  # type: ignore[method-assign]

    with pytest.raises(RepositoryBindingError, match="snapshot_not_fresh"):
        asyncio.run(
            store.get_context_package(
                ContextPackageQuery(query="find native replay"),
                binding=binding,
            )
        )


def test_refresh_status_reports_skipped_completed_and_failed_runs() -> None:
    skipped = _refresh_status(
        IngestionRunSummary(
            run_id="run:skipped",
            repository_id="repo:test",
            repository_root="C:/sample",
            stage="Completed",
            language="csharp",
            parser_name="test",
            embedding_provider="none",
            embedding_model="none",
            stats={
                "parsed_node_count": 4,
                "written_node_count": 0,
                "written_relationship_count": 0,
                "written_content_count": 0,
                "written_embedding_count": 0,
                "written_summary_count": 0,
            },
        )
    )
    assert skipped["status"] == "skipped"
    assert skipped["changed"] is False
    assert skipped["latest_run_id"] == "run:skipped"

    completed = _refresh_status(
        IngestionRunSummary(
            run_id="run:completed",
            repository_id="repo:test",
            repository_root="C:/sample",
            stage="Completed",
            language="csharp",
            parser_name="test",
            embedding_provider="none",
            embedding_model="none",
            stats={"parsed_node_count": 4, "written_node_count": 1},
        )
    )
    assert completed["status"] == "completed"
    assert completed["changed"] is True

    failed = _refresh_status(
        IngestionRunSummary(
            run_id="run:failed",
            repository_id="repo:test",
            repository_root="C:/sample",
            stage="Failed",
            language="csharp",
            parser_name="test",
            embedding_provider="none",
            embedding_model="none",
            error_diagnostic_count=1,
        )
    )
    assert failed["status"] == "failed"
    assert "codemesh refresh" in failed["recommended_action"]


def test_graph_storage_key_uses_repository_prefix() -> None:
    assert storage_key("repo:test", "node:one") == "repo:test:node:one"


@pytest.mark.parametrize("repository_id", [None, "", "snapshot:'}) RETURN secret //"])
def test_lexical_query_scopes_before_projection_and_parameterizes_input(
    monkeypatch, repository_id
) -> None:
    calls = []
    node = {"id": "node:test", "repositoryId": repository_id}

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def run(self, query, **parameters):
            calls.append((query, parameters))
            return self

        async def data(self):
            return [{"node": node}]

    class Driver:
        def session(self, **kwargs):
            return Session()

    store = Neo4jGraphStore(Settings.from_env())
    monkeypatch.setattr(store, "_neo4j", lambda: Driver())
    search_text = "Download 'quoted' input"
    result = asyncio.run(
        store.search_context_nodes(search_text, ["method"], repository_id, 12)
    )
    assert result == [node]
    query, parameters = calls[0]
    assert parameters == {
        "search_text": search_text.casefold(),
        "search_terms": ["download", "quoted", "input"],
        "kinds": ["method"],
        "repository_id": repository_id,
        "limit": 12,
    }
    assert search_text not in query
    if repository_id is None:
        assert "repositoryId" not in query
    else:
        assert "repositoryId: $repository_id" in query.split("WITH n", 1)[0]
        if repository_id:
            assert repository_id not in query


def test_lexical_terms_normalizes_and_deduplicates_query_words() -> None:
    assert lexical_terms("Repository cleanup, repository records") == [
        "repository",
        "cleanup",
        "records",
    ]
    assert callable(Neo4jGraphStore.delete_repository)


def test_node_summary_normalizer_preserves_generated_metadata() -> None:
    summary = normalize_node_summary(
        {
            "_id": "summary:test",
            "repositoryId": "repo:test",
            "nodeId": "node:test",
            "stableKey": "stable:test",
            "kind": "Method",
            "name": "DownloadAsync",
            "contentHash": "content:test",
            "summaryKind": "symbol",
            "summary": "Downloads subtitles for a video URL.",
            "tags": ["download", "subtitles"],
            "confidence": "high",
            "provider": "lmstudio",
            "model": "qwen/qwen3.5-9b",
            "promptVersion": "node-summary-v1",
            "metadata": {"language": "csharp"},
        }
    )

    assert summary["id"] == "summary:test"
    assert summary["repository_id"] == "repo:test"
    assert summary["summary"] == "Downloads subtitles for a video URL."
    assert summary["tags"] == ["download", "subtitles"]
    assert summary["provider"] == "lmstudio"
    assert summary["metadata"] == {"language": "csharp"}


def test_node_summary_lookup_falls_back_when_content_hash_differs() -> None:
    store = MongoNodeSummaryStore.__new__(MongoNodeSummaryStore)
    store._settings = Settings.from_env()
    store._mongo_client = FakeMongoClient()
    collection = FakeSummaryCollection()
    store._mongo_client.databases[store._settings.mongo_database] = {
        store._settings.mongo_node_summaries_collection: collection
    }

    summary = asyncio.run(
        store.get_node_summary("repo:test", "node:test", "declaration-hash")
    )

    assert summary is not None
    assert summary["content_hash"] == "symbol-hash"
    assert collection.queries == [
        {
            "repositoryId": "repo:test",
            "nodeId": "node:test",
            "status": "completed",
            "contentHash": "declaration-hash",
        },
        {"repositoryId": "repo:test", "nodeId": "node:test", "status": "completed"},
    ]


def test_node_summary_coverage_counts_status_kind_and_provider_model() -> None:
    store = MongoNodeSummaryStore.__new__(MongoNodeSummaryStore)
    store._settings = Settings.from_env()
    store._mongo_client = FakeMongoClient()
    collection = FakeSummaryCollection(
        [
            {
                "_id": "summary:completed",
                "repositoryId": "repo:test",
                "nodeId": "node:completed",
                "kind": "Method",
                "status": "completed",
                "provider": "lmstudio",
                "model": "qwen/qwen2.5-coder-14b",
                "promptVersion": "node-summary-v1",
            },
            {
                "_id": "summary:failed",
                "repositoryId": "repo:test",
                "nodeId": "node:failed",
                "kind": "Class",
                "status": "failed",
                "provider": "lmstudio",
                "model": "qwen/qwen2.5-coder-14b",
                "promptVersion": "node-summary-v1",
                "error": "model failed",
            },
            {
                "_id": "summary:other",
                "repositoryId": "repo:other",
                "nodeId": "node:other",
                "kind": "Method",
                "status": "completed",
            },
        ]
    )
    store._mongo_client.databases[store._settings.mongo_database] = {
        store._settings.mongo_node_summaries_collection: collection
    }

    coverage = asyncio.run(store.summary_coverage("repo:test"))

    assert coverage["total_count"] == 2
    assert coverage["completed_count"] == 1
    assert coverage["failed_count"] == 1
    assert coverage["status_counts"] == {"completed": 1, "failed": 1}
    assert coverage["kind_counts"] == {"Method": 1, "Class": 1}
    assert coverage["provider_model_counts"] == {
        "lmstudio/qwen/qwen2.5-coder-14b/node-summary-v1": 2
    }
    assert coverage["provider_model_count_details"] == [
        {
            "provider": "lmstudio",
            "model": "qwen/qwen2.5-coder-14b",
            "prompt_version": "node-summary-v1",
            "count": 2,
        }
    ]
    assert coverage["recent_failures"][0]["error"] == "model failed"


def test_content_store_close_closes_cached_mongo_client() -> None:
    store = MongoContentStore.__new__(MongoContentStore)
    client = FakeMongoClient()
    store._mongo_client = client

    asyncio.run(store.close())

    assert client.closed is True
    assert store._mongo_client is None


def test_graph_store_close_closes_cached_driver() -> None:
    store = Neo4jGraphStore.__new__(Neo4jGraphStore)
    driver = FakeNeo4jDriver()
    store._neo4j_driver = driver

    asyncio.run(store.close())

    assert driver.closed is True
    assert store._neo4j_driver is None


def test_read_store_close_delegates_to_owned_stores() -> None:
    store = CodeMeshReadStore.__new__(CodeMeshReadStore)
    graph = FakeClosable()
    content = FakeClosable()
    store._graph = graph
    store._content = content

    asyncio.run(store.close())

    assert graph.closed is True
    assert content.closed is True


def test_read_store_delete_repository_resolves_alias_and_cleans_all_stores() -> None:
    store = CodeMeshReadStore.__new__(CodeMeshReadStore)
    graph = FakeCleanupStore()
    content = FakeContentCleanupStore()
    vector = FakeCleanupStore()
    summaries = FakeCleanupStore()
    store._graph = graph
    store._content = content
    store._vectors = vector
    store._summaries = summaries

    result = asyncio.run(store.delete_repository("sample_repo"))

    assert result.repository_id == "repo:test"
    assert result.deleted is True
    assert graph.deleted_repository_ids == ["repo:test"]
    assert content.deleted_repository_ids == ["repo:test"]
    assert vector.deleted_repository_ids == ["repo:test"]
    assert summaries.deleted_repository_ids == ["repo:test"]


class FakeMongoClient:
    def __init__(self) -> None:
        self.closed = False
        self.databases: dict[str, Any] = {}

    def close(self) -> None:
        self.closed = True

    def __getitem__(self, name: str) -> Any:
        return self.databases[name]


class FakeSummaryCollection:
    def __init__(self, documents: list[dict[str, Any]] | None = None) -> None:
        self.queries: list[dict[str, Any]] = []
        self.documents = documents or [
            {
                "_id": "summary:test",
                "repositoryId": "repo:test",
                "nodeId": "node:test",
                "contentHash": "symbol-hash",
                "summary": "Fallback summary.",
                "status": "completed",
            }
        ]

    def find_one(
        self, query: dict[str, Any], sort: Any = None
    ) -> dict[str, Any] | None:
        self.queries.append(dict(query))
        if "contentHash" in query:
            return None

        return dict(self.documents[0]) if self.documents else None

    def count_documents(self, query: dict[str, Any]) -> int:
        return len(_matching_documents(self.documents, query))

    def aggregate(self, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        documents = _matching_documents(self.documents, pipeline[0].get("$match", {}))
        group = pipeline[1].get("$group", {})
        group_id = group.get("_id")
        counts: dict[Any, int] = {}
        for document in documents:
            if isinstance(group_id, str):
                key: Any = document.get(group_id.removeprefix("$"))
            elif isinstance(group_id, dict):
                key = {
                    name: document.get(str(field).removeprefix("$"))
                    for name, field in group_id.items()
                }
                key = tuple(sorted(key.items()))
            else:
                key = None
            counts[key] = counts.get(key, 0) + 1

        results = []
        for key, count in counts.items():
            if isinstance(key, tuple):
                key = dict(key)
            results.append({"_id": key, "count": count})
        return results

    def find(self, query: dict[str, Any]) -> "FakeSummaryCursor":
        return FakeSummaryCursor(_matching_documents(self.documents, query))


class FakeSummaryCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    def sort(self, *args: Any) -> "FakeSummaryCursor":
        return self

    def limit(self, limit: int) -> list[dict[str, Any]]:
        return [dict(document) for document in self._documents[:limit]]


def _matching_documents(
    documents: list[dict[str, Any]], query: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        document
        for document in documents
        if all(document.get(key) == value for key, value in query.items())
    ]


class FakeNeo4jDriver:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeClosable:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeCleanupStore:
    def __init__(self) -> None:
        self.deleted_repository_ids: list[str] = []

    async def delete_repository(self, repository_id: str) -> None:
        self.deleted_repository_ids.append(repository_id)


class FakeContentCleanupStore(FakeCleanupStore):
    async def get_repository(self, repository_id: str) -> Any:
        assert repository_id == "sample_repo"
        return type(
            "Repository",
            (),
            {
                "repository_id": "repo:test",
            },
        )()


class FakeAsyncClient:
    payload: dict[str, Any] = {}
    last_json: dict[str, Any] | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def get(self, url: str) -> "FakeHttpResponse":
        return FakeHttpResponse(self.payload)

    async def post(
        self, url: str, json: dict[str, Any], **kwargs: Any
    ) -> "FakeHttpResponse":
        self.__class__.last_json = json
        return FakeHttpResponse(self.payload)


class FakeHttpResponse:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return self._payload
