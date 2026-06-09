from __future__ import annotations

import asyncio
from typing import Any

from codemesh_agent_access import embeddings as embeddings_module
from codemesh_agent_access.content_store import (
    MongoContentStore,
    normalize_ingestion_run,
    normalize_repository,
    repository_alias,
)
from codemesh_agent_access.config import Settings
from codemesh_agent_access.embeddings import QueryEmbeddingProvider, _listed_model_ids, model_provider
from codemesh_agent_access.graph_store import Neo4jGraphStore, storage_key
from codemesh_agent_access.store import CodeMeshReadStore
from codemesh_agent_access.summary_store import MongoNodeSummaryStore, normalize_node_summary
from codemesh_agent_access.vector_store import qdrant_filter_for


def test_model_provider_normalizes_lm_studio_aliases() -> None:
    assert model_provider("lmstudio") == "lmstudio"
    assert model_provider("LM-Studio") == "lmstudio"
    assert model_provider("lm_studio") == "lmstudio"
    assert model_provider(" ollama ") == "ollama"


def test_settings_uses_provider_default_when_embedding_model_is_blank(monkeypatch) -> None:
    monkeypatch.setenv("CODEMESH_MODEL_PROVIDER", "lmstudio")
    monkeypatch.setenv("CODEMESH_EMBEDDING_MODEL", "")

    settings = Settings.from_env()

    assert settings.embedding_model == "text-embedding-nomic-embed-text-v1.5"
    assert settings.mongo_node_summaries_collection == "node_summaries"


def test_model_list_parsing_supports_ollama_and_lm_studio_shapes() -> None:
    assert _listed_model_ids(
        "ollama",
        {"models": [{"name": "nomic-embed-text:latest"}, {"model": "other"}]},
    ) == {"nomic-embed-text:latest", "other"}
    assert _listed_model_ids(
        "lmstudio",
        {"data": [{"id": "text-embedding-nomic-embed-text-v1.5"}]},
    ) == {"text-embedding-nomic-embed-text-v1.5"}


def test_query_embedding_health_degrades_when_configured_model_is_missing(monkeypatch) -> None:
    monkeypatch.setenv("CODEMESH_MODEL_PROVIDER", "lmstudio")
    monkeypatch.setenv("CODEMESH_EMBEDDING_MODEL", "expected-model")
    monkeypatch.setattr(embeddings_module.httpx, "AsyncClient", FakeAsyncClient)

    FakeAsyncClient.payload = {"data": [{"id": "expected-model"}]}
    healthy = asyncio.run(QueryEmbeddingProvider(Settings.from_env()).health())
    assert healthy["status"] == "healthy"

    FakeAsyncClient.payload = {"data": [{"id": "other-model"}]}
    degraded = asyncio.run(QueryEmbeddingProvider(Settings.from_env()).health())
    assert degraded["status"] == "degraded"
    assert degraded["detail"] == "Configured embedding model is not listed by the model provider."


def test_qdrant_filter_maps_exact_payload_matches() -> None:
    assert qdrant_filter_for({}) is None
    assert qdrant_filter_for({"repositoryId": "repo:test", "kind": "Method"}) == {
        "must": [
            {"key": "repositoryId", "match": {"value": "repo:test"}},
            {"key": "kind", "match": {"value": "Method"}},
        ]
    }


def test_repository_alias_splits_paths_and_camel_case() -> None:
    assert repository_alias("D:/source/repos/YoutubeDownloader") == "d_source_repos_youtube_downloader"
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
            "stats": {"ParsedNodeCount": "7", "writtenEmbeddingCount": "5"},
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
    }


def test_graph_storage_key_uses_repository_prefix() -> None:
    assert storage_key("repo:test", "node:one") == "repo:test:node:one"


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

    summary = asyncio.run(store.get_node_summary("repo:test", "node:test", "declaration-hash"))

    assert summary is not None
    assert summary["content_hash"] == "symbol-hash"
    assert collection.queries == [
        {"repositoryId": "repo:test", "nodeId": "node:test", "status": "completed", "contentHash": "declaration-hash"},
        {"repositoryId": "repo:test", "nodeId": "node:test", "status": "completed"},
    ]


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


class FakeMongoClient:
    def __init__(self) -> None:
        self.closed = False
        self.databases: dict[str, Any] = {}

    def close(self) -> None:
        self.closed = True

    def __getitem__(self, name: str) -> Any:
        return self.databases[name]


class FakeSummaryCollection:
    def __init__(self) -> None:
        self.queries: list[dict[str, Any]] = []

    def find_one(self, query: dict[str, Any], sort: Any = None) -> dict[str, Any] | None:
        self.queries.append(dict(query))
        if "contentHash" in query:
            return None

        return {
            "_id": "summary:test",
            "repositoryId": "repo:test",
            "nodeId": "node:test",
            "contentHash": "symbol-hash",
            "summary": "Fallback summary.",
            "status": "completed",
        }


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


class FakeAsyncClient:
    payload: dict[str, Any] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def get(self, url: str) -> "FakeHttpResponse":
        return FakeHttpResponse(self.payload)


class FakeHttpResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return self._payload
