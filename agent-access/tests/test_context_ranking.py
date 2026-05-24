from __future__ import annotations

import asyncio

from codemesh_agent_access.config import Settings
from codemesh_agent_access.models import ContextHit, ContextQuery
from codemesh_agent_access.store import CodeMeshReadStore, _ranked_unique_hits


def test_vector_search_expands_parameter_declaration_to_method_context() -> None:
    store = FakeReadStore()

    response = asyncio.run(
        store.search_context(
            ContextQuery(
                query="download video subtitles",
                repository_id="repo:test",
                limit=1,
                vector=[1.0, 0.0],
                include_context_relationships=True,
            )
        )
    )

    assert len(response.hits) == 1
    hit = response.hits[0]
    assert hit.node_id == "csharp:method:Sample.Downloader.DownloadAsync(System.String)"
    assert hit.kind == "Method"
    assert hit.file_path == "Downloader.cs"
    assert hit.start_line == 10
    assert hit.end_line == 24
    assert hit.content_hash == "method-body"
    assert hit.preview == "public Task DownloadAsync(string url) { return Task.CompletedTask; }"
    assert hit.score_components["vector_score"] == 0.6
    assert hit.score_components["kind_weight"] > 1.0
    assert hit.expanded_context is not None
    assert hit.expanded_context["source"]["kind"] == "Declaration"
    assert hit.expanded_context["selected"]["kind"] == "Method"
    assert hit.expanded_context["declaration"]["start_line"] == 10
    assert hit.expanded_context["relationships"] == [
        {
            "kind": "Contains",
            "label": "contains",
            "direction": "out",
            "source_node_id": "csharp:method:Sample.Downloader.DownloadAsync(System.String)",
            "target_node_id": "csharp:param:Sample.Downloader.DownloadAsync(System.String):0:url",
            "other": {
                "node_id": "csharp:param:Sample.Downloader.DownloadAsync(System.String):0:url",
                "kind": "Parameter",
                "name": "url",
                "file_path": "Downloader.cs",
                "start_line": 0,
                "end_line": 0,
            },
        }
    ]


def test_vector_search_can_disable_context_expansion() -> None:
    store = FakeReadStore()

    response = asyncio.run(
        store.search_context(
            ContextQuery(
                query="download video subtitles",
                repository_id="repo:test",
                limit=1,
                vector=[1.0, 0.0],
                expand_context=False,
            )
        )
    )

    assert len(response.hits) == 1
    hit = response.hits[0]
    assert hit.node_id == store.parameter_declaration["id"]
    assert hit.kind == "Declaration"
    assert hit.expanded_context is None


def test_ranked_unique_hits_keeps_best_expanded_context() -> None:
    lower = ContextHit(
        node_id="same",
        stable_key="same",
        kind="Parameter",
        file_path="Demo.cs",
        start_line=20,
        end_line=20,
        score=0.3,
    )
    higher = ContextHit(
        node_id="same",
        stable_key="same",
        kind="Method",
        file_path="Demo.cs",
        start_line=10,
        end_line=30,
        score=0.8,
    )

    assert _ranked_unique_hits([lower, higher], 5) == [higher]


class FakeReadStore(CodeMeshReadStore):
    def __init__(self) -> None:
        super().__init__(
            Settings(
                host="127.0.0.1",
                port=8080,
                neo4j_uri="bolt://unused",
                neo4j_user="neo4j",
                neo4j_password="codemesh",
                neo4j_database="neo4j",
                mongo_uri="mongodb://unused",
                mongo_database="codemesh",
                mongo_content_collection="content",
                mongo_repositories_collection="repositories",
                mongo_ingestion_runs_collection="ingestion_runs",
                qdrant_url="http://unused",
                qdrant_collection="codemesh-code",
                model_provider="none",
                ollama_url="http://unused",
                embedding_model="nomic-embed-text:latest",
            )
        )
        self.parameter_declaration = _node(
            "csharp:decl:csharp:param:Sample.Downloader.DownloadAsync(System.String):0:url:Downloader.cs:10:34",
            "Declaration",
            "url",
            "parameter-declaration",
            start_line=10,
            end_line=10,
        )
        self.parameter_symbol = _node(
            "csharp:param:Sample.Downloader.DownloadAsync(System.String):0:url",
            "Parameter",
            "url",
            "parameter-symbol",
        )
        self.method_symbol = _node(
            "csharp:method:Sample.Downloader.DownloadAsync(System.String)",
            "Method",
            "DownloadAsync",
            "method-symbol",
        )
        self.method_declaration = _node(
            "csharp:decl:csharp:method:Sample.Downloader.DownloadAsync(System.String):Downloader.cs:10:5",
            "Declaration",
            "DownloadAsync",
            "method-body",
            start_line=10,
            end_line=24,
        )

    async def _search_qdrant(
        self,
        vector: list[float],
        limit: int,
        filters: dict[str, str],
    ) -> list[dict[str, object]]:
        return [
            {
                "nodeId": self.parameter_declaration["id"],
                "contentHash": self.parameter_declaration["contentHash"],
                "repositoryId": "repo:test",
                "score": 0.6,
                "preview": "string url",
            }
        ]

    async def _get_node_properties(
        self,
        node_id: str,
        repository_id: str | None = None,
    ) -> dict[str, object] | None:
        nodes = {
            self.parameter_declaration["id"]: self.parameter_declaration,
            self.parameter_symbol["id"]: self.parameter_symbol,
            self.method_symbol["id"]: self.method_symbol,
            self.method_declaration["id"]: self.method_declaration,
        }
        return nodes.get(node_id)

    async def _get_context_candidates(
        self,
        node_id: str,
        repository_id: str | None = None,
        depth: int = 4,
    ) -> list[dict[str, object]]:
        if node_id != self.parameter_declaration["id"]:
            return []

        return [
            {"node": self.parameter_symbol, "distance": 0, "reason": "defines"},
            {"node": self.method_symbol, "distance": 1, "reason": "defined_ancestor"},
        ]

    async def _get_primary_declaration_node(
        self,
        node: dict[str, object],
        repository_id: str | None = None,
    ) -> dict[str, object] | None:
        if node.get("id") == self.method_symbol["id"]:
            return self.method_declaration
        return None

    async def _get_context_relationship_summaries(
        self,
        node_id: str,
        repository_id: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, object]]:
        if node_id != self.method_symbol["id"]:
            return []

        return [
            {
                "kind": "Contains",
                "label": "contains",
                "direction": "out",
                "source_node_id": self.method_symbol["id"],
                "target_node_id": self.parameter_symbol["id"],
                "other": {
                    "node_id": self.parameter_symbol["id"],
                    "kind": "Parameter",
                    "name": "url",
                    "file_path": "Downloader.cs",
                    "start_line": 0,
                    "end_line": 0,
                },
            }
        ][:limit]

    async def _get_content(self, content_hash: str) -> dict[str, object] | None:
        contents = {
            "method-body": {
                "hash": "method-body",
                "text": "public Task DownloadAsync(string url) { return Task.CompletedTask; }",
                "media_type": "text/x-csharp-fragment",
            }
        }
        return contents.get(content_hash)


def _node(
    node_id: str,
    kind: str,
    name: str,
    content_hash: str,
    start_line: int = 0,
    end_line: int = 0,
) -> dict[str, object]:
    return {
        "id": node_id,
        "stableKey": node_id,
        "kind": kind,
        "name": name,
        "language": "csharp",
        "project": "Sample",
        "repositoryId": "repo:test",
        "ingestionRunId": "run:test",
        "filePath": "Downloader.cs",
        "startLine": start_line,
        "startColumn": 1,
        "endLine": end_line,
        "endColumn": 1,
        "contentHash": content_hash,
        "metadataJson": "{}",
    }
