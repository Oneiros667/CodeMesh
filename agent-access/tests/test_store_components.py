from __future__ import annotations

import asyncio

from codemesh_agent_access.content_store import (
    MongoContentStore,
    normalize_ingestion_run,
    normalize_repository,
    repository_alias,
)
from codemesh_agent_access.embeddings import model_provider
from codemesh_agent_access.graph_store import Neo4jGraphStore, storage_key
from codemesh_agent_access.store import CodeMeshReadStore
from codemesh_agent_access.vector_store import qdrant_filter_for


def test_model_provider_normalizes_lm_studio_aliases() -> None:
    assert model_provider("lmstudio") == "lmstudio"
    assert model_provider("LM-Studio") == "lmstudio"
    assert model_provider("lm_studio") == "lmstudio"
    assert model_provider(" ollama ") == "ollama"


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

    def close(self) -> None:
        self.closed = True


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
