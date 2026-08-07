from __future__ import annotations

import asyncio

from codemesh_agent_access.config import Settings
from codemesh_agent_access.graph_store import lexical_terms
from codemesh_agent_access.models import (
    ContextHit,
    ContextPackageQuery,
    ContextQuery,
    IngestionRunListResponse,
    IngestionRunSummary,
    RepositorySummary,
    SymbolQuery,
)
from codemesh_agent_access.store import (
    CodeMeshReadStore,
    _diversify_lexical_nodes,
    _lexical_score,
    _prioritize_context_relationships,
    _ranked_unique_hits,
)


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
                context_relationship_limit=1,
            )
        )
    )

    assert len(response.hits) == 1
    assert response.diagnostics == {
        "mode": "hybrid",
        "embedding_attempted": False,
        "embedding_source": "provided",
        "model_provider": "none",
        "vector_available": True,
        "vector_hit_count": 1,
        "lexical_hit_count": 1,
        "summary_hit_count": 0,
        "vector_candidate_count": 1,
        "lexical_candidate_count": 1,
        "summary_candidate_count": 0,
        "lexical_fallback": False,
        "hit_count": 1,
    }
    hit = response.hits[0]
    assert hit.node_id == "csharp:method:Sample.Downloader.DownloadAsync(System.String)"
    assert hit.kind == "Method"
    assert hit.file_path == "Downloader.cs"
    assert hit.start_line == 10
    assert hit.end_line == 24
    assert hit.content_hash == "method-body"
    assert (
        hit.preview
        == "public Task DownloadAsync(string url) { return Task.CompletedTask; }"
    )
    assert hit.score_components["vector_score"] == 0.6
    assert hit.score_components["kind_weight"] > 1.0
    assert hit.expanded_context is not None
    assert hit.expanded_context["source"]["kind"] == "Declaration"
    assert hit.expanded_context["selected"]["kind"] == "Method"
    assert hit.expanded_context["declaration"]["start_line"] == 10
    assert hit.expanded_context["relationships"] == [
        {
            "kind": "Defines",
            "label": "defines",
            "direction": "in",
            "source_node_id": "csharp:decl:csharp:method:Sample.Downloader.DownloadAsync(System.String):Downloader.cs:10:5",
            "target_node_id": "csharp:method:Sample.Downloader.DownloadAsync(System.String)",
            "other": {
                "node_id": "csharp:decl:csharp:method:Sample.Downloader.DownloadAsync(System.String):Downloader.cs:10:5",
                "kind": "Declaration",
                "name": "DownloadAsync",
                "file_path": "Downloader.cs",
                "start_line": 10,
                "end_line": 24,
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
    assert hit.node_id == store.method_symbol["id"]
    assert hit.kind == "Method"
    assert hit.expanded_context is not None
    assert hit.expanded_context["reason"] == "self"
    assert (
        hit.expanded_context["source"]["node_id"]
        == hit.expanded_context["selected"]["node_id"]
    )


def test_vector_search_reports_lexical_fallback_when_vector_has_no_hits() -> None:
    store = FakeReadStore()

    response = asyncio.run(
        store.search_context(
            ContextQuery(
                query="download video subtitles",
                repository_id="repo:test",
                limit=1,
                vector=[0.0, 0.0],
            )
        )
    )

    assert len(response.hits) == 1
    assert (
        response.hits[0].node_id
        == "csharp:method:Sample.Downloader.DownloadAsync(System.String)"
    )
    assert response.diagnostics == {
        "mode": "lexical",
        "embedding_attempted": False,
        "embedding_source": "provided",
        "model_provider": "none",
        "vector_available": True,
        "vector_hit_count": 0,
        "lexical_hit_count": 1,
        "summary_hit_count": 0,
        "vector_candidate_count": 0,
        "lexical_candidate_count": 1,
        "summary_candidate_count": 0,
        "lexical_fallback": True,
        "hit_count": 1,
    }


def test_summary_search_contributes_context_hits() -> None:
    store = FakeReadStore()
    store.enable_summary_search = True

    response = asyncio.run(
        store.search_context(
            ContextQuery(
                query="subtitles",
                repository_id="repo:test",
                limit=1,
                expand_context=False,
            )
        )
    )

    assert len(response.hits) == 1
    hit = response.hits[0]
    assert hit.node_id == store.method_symbol["id"]
    assert hit.score_components["summary_score"] > 0
    assert response.diagnostics["summary_hit_count"] == 1
    assert response.diagnostics["summary_candidate_count"] == 1


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


def test_lexical_score_ranks_multi_term_coverage() -> None:
    query = "repository cleanup removes indexed data"
    primary = {
        "id": "csharp:method:RepositoryCleanupService.DeleteRepositoryAsync",
        "stableKey": "csharp:method:RepositoryCleanupService.DeleteRepositoryAsync",
        "name": "DeleteRepositoryAsync",
        "filePath": "src/CodeMesh.Ingestion/RepositoryCleanupService.cs",
    }
    partial = {
        "id": "csharp:type:RepositoryIndexRecord",
        "stableKey": "csharp:type:RepositoryIndexRecord",
        "name": "RepositoryIndexRecord",
        "filePath": "src/CodeMesh.Domain/IngestionContracts.cs",
    }

    assert _lexical_score(primary, query) > _lexical_score(partial, query)


def test_lexical_score_prefers_terms_in_symbol_and_file_names() -> None:
    query = "download multi settings"
    explicit_boundary = {
        "id": "csharp:type:YoutubeDownloader.DownloadMultipleSetupViewModel",
        "stableKey": "csharp:type:YoutubeDownloader.DownloadMultipleSetupViewModel",
        "name": "DownloadMultipleSetupViewModel",
        "filePath": "YoutubeDownloader/DownloadMultipleSetupViewModel.cs",
    }
    incidental_signature = {
        "id": "csharp:ctor:YoutubeDownloader.AuthSetupViewModel(SettingsService)",
        "stableKey": "csharp:ctor:YoutubeDownloader.AuthSetupViewModel(SettingsService)",
        "name": "AuthSetupViewModel",
        "filePath": "YoutubeDownloader/AuthSetupViewModel.cs",
    }

    assert _lexical_score(explicit_boundary, query) > _lexical_score(
        incidental_signature, query
    )


def test_lexical_terms_remove_grammatical_noise() -> None:
    assert lexical_terms("trace the callers of a method and its writes") == [
        "trace",
        "callers",
        "method",
        "its",
        "writes",
    ]


def test_lexical_candidates_cover_distinct_files_before_repeating() -> None:
    nodes = [
        {"id": "a-1", "filePath": "A.cs"},
        {"id": "a-2", "filePath": "A.cs"},
        {"id": "b-1", "filePath": "B.cs"},
        {"id": "c-1", "filePath": "C.cs"},
        {"id": "b-2", "filePath": "B.cs"},
    ]

    selected = _diversify_lexical_nodes(nodes, 5)

    assert [node["id"] for node in selected] == [
        "a-1",
        "b-1",
        "c-1",
        "a-2",
        "b-2",
    ]


def test_context_relationship_prioritization_prefers_agent_useful_edges() -> None:
    relationships = [
        _relationship("Contains", "out", "parameter", start_line=10),
        _relationship("Reads", "out", "field", start_line=7),
        _relationship("Invokes", "out", "callee", start_line=30),
        _relationship("UsesType", "out", "type", start_line=1),
        _relationship("Writes", "out", "property", start_line=8),
        _relationship("Invokes", "in", "caller", start_line=20),
        _relationship("Contains", "in", "owner", start_line=4),
        _relationship("Defines", "in", "declaration", start_line=10),
    ]

    ordered = _prioritize_context_relationships(relationships, 5)

    assert [
        (item["kind"], item["direction"], item["other"]["name"]) for item in ordered
    ] == [
        ("Defines", "in", "declaration"),
        ("Contains", "in", "owner"),
        ("Invokes", "in", "caller"),
        ("Invokes", "out", "callee"),
        ("Writes", "out", "property"),
    ]


def test_context_relationship_prioritization_applies_group_limits() -> None:
    relationships = [
        _relationship("Defines", "in", "declaration", start_line=10),
        _relationship("Contains", "in", "owner", start_line=4),
        _relationship("Invokes", "in", "caller-a", start_line=20),
        _relationship("Invokes", "in", "caller-b", start_line=30),
        _relationship("Invokes", "out", "callee", start_line=40),
        _relationship("Writes", "out", "property", start_line=8),
        _relationship("Reads", "out", "field-a", start_line=7),
        _relationship("Reads", "out", "field-b", start_line=9),
    ]

    ordered = _prioritize_context_relationships(
        relationships,
        8,
        {"callers": 1, "reads": 1, "writes": 0},
    )

    assert [
        (item["kind"], item["direction"], item["other"]["name"]) for item in ordered
    ] == [
        ("Defines", "in", "declaration"),
        ("Contains", "in", "owner"),
        ("Invokes", "in", "caller-a"),
        ("Invokes", "out", "callee"),
        ("Reads", "out", "field-a"),
    ]


def test_context_package_includes_snippet_relationships_and_registry_metadata() -> None:
    store = FakeReadStore()

    package = asyncio.run(
        store.get_context_package(
            ContextPackageQuery(
                query="download video subtitles",
                repository_id="repo:test",
                limit=1,
                max_characters=48,
                vector=[1.0, 0.0],
                relationship_limit=7,
                read_limit=0,
                contains_limit=1,
            )
        )
    )

    assert package.repository is not None
    assert package.repository["repository_id"] == "repo:test"
    assert package.latest_run is not None
    assert package.latest_run["run_id"] == "run:test"
    assert package.validation_recommendations == [
        {
            "id": "dotnet-build",
            "command": "dotnet build",
            "reason": (
                "Build the indexed .NET repository from its root. Inspect "
                "repository-owned workflow and test configuration before "
                "claiming broader validation."
            ),
            "applies_to": ["Downloader.cs"],
        }
    ]
    assert package.total_snippet_characters <= 48
    assert len(package.items) == 1

    item = package.items[0]
    assert (
        item.hit.node_id
        == "csharp:method:Sample.Downloader.DownloadAsync(System.String)"
    )
    assert item.node is not None
    assert item.node["id"] == item.hit.node_id
    assert item.content == {
        "hash": "method-body",
        "media_type": "text/x-csharp-fragment",
        "created_at": None,
        "updated_at": None,
    }
    assert item.summary is not None
    assert item.summary["summary"] == "Downloads subtitles for a video URL."
    assert item.summary["provider"] == "test"
    assert item.snippet is not None
    assert item.snippet.endswith("...<trimmed>")
    assert [(item["kind"], item["direction"]) for item in item.relationships[:5]] == [
        ("Defines", "in"),
        ("Contains", "in"),
        ("Invokes", "in"),
        ("Invokes", "out"),
        ("Writes", "out"),
    ]
    assert item.relationship_groups["contains"][0]["kind"] == "Contains"
    assert len(item.relationship_groups["contains"]) == 1
    assert (
        item.relationship_groups["callees"][0]["target_node_id"]
        == "csharp:method:Sample.Downloader.Normalize(System.String)"
    )
    assert (
        item.relationship_groups["callers"][0]["source_node_id"]
        == "csharp:method:Sample.Program.Main(System.String[])"
    )
    assert item.relationship_groups["reads"] == []
    assert (
        item.relationship_groups["writes"][0]["target_node_id"]
        == "csharp:property:Sample.Downloader.LastUrl"
    )
    assert item.rationale["rank"] == 1
    assert item.rationale["expanded"] is True


def test_context_package_accepts_repository_alias() -> None:
    store = FakeReadStore()

    package = asyncio.run(
        store.get_context_package(
            ContextPackageQuery(
                query="download video subtitles",
                repository_id="sample_repo",
                limit=1,
                vector=[1.0, 0.0],
            )
        )
    )

    assert package.query.repository_id == "repo:test"
    assert package.repository is not None
    assert package.repository["alias"] == "sample_repo"
    assert package.latest_run is not None
    assert package.latest_run["repository_id"] == "repo:test"
    assert package.items[0].hit.repository_id == "repo:test"


def test_symbol_search_resolves_alias_and_returns_declaration() -> None:
    store = FakeReadStore()

    response = asyncio.run(
        store.search_symbols(
            SymbolQuery(
                query="DownloadAsync",
                repository_id="sample_repo",
                limit=5,
                kinds=["Method"],
            )
        )
    )

    assert response.query.repository_id == "repo:test"
    assert len(response.symbols) == 1
    symbol = response.symbols[0]
    assert (
        symbol.node["id"]
        == "csharp:method:Sample.Downloader.DownloadAsync(System.String)"
    )
    assert (
        symbol.node["metadata"]["display"] == "Sample.Downloader.DownloadAsync(string)"
    )
    assert symbol.declaration is not None
    assert symbol.declaration["kind"] == "Declaration"
    assert symbol.score > 0


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
                mongo_node_summaries_collection="node_summaries",
                qdrant_url="http://unused",
                qdrant_collection="codemesh-code",
                model_provider="none",
                ollama_url="http://unused",
                lm_studio_url="http://unused/v1",
                embedding_model="nomic-embed-text-v2-moe:latest",
            )
        )
        self._vectors = FakeVectorClient(self)
        self.enable_summary_search = False
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
        self.method_symbol["metadataJson"] = (
            '{"nodeRole":"symbol","display":"Sample.Downloader.DownloadAsync(string)",'
            '"namespace":"Sample","containingType":"Sample.Downloader"}'
        )
        self.method_declaration = _node(
            "csharp:decl:csharp:method:Sample.Downloader.DownloadAsync(System.String):Downloader.cs:10:5",
            "Declaration",
            "DownloadAsync",
            "method-body",
            start_line=10,
            end_line=24,
        )

    async def _search_symbol_nodes(self, query: SymbolQuery) -> list[dict[str, object]]:
        nodes = [self.method_symbol, self.parameter_symbol]
        kinds = {kind.casefold() for kind in query.kinds}
        if kinds:
            nodes = [node for node in nodes if str(node["kind"]).casefold() in kinds]
        return nodes

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
        group_limits: dict[str, int] | None = None,
    ) -> list[dict[str, object]]:
        if node_id != self.method_symbol["id"]:
            return []

        relationships = [
            {
                "kind": "Defines",
                "label": "defines",
                "direction": "in",
                "source_node_id": self.method_declaration["id"],
                "target_node_id": self.method_symbol["id"],
                "other": {
                    "node_id": self.method_declaration["id"],
                    "kind": "Declaration",
                    "name": "DownloadAsync",
                    "file_path": "Downloader.cs",
                    "start_line": 10,
                    "end_line": 24,
                },
            },
            {
                "kind": "Contains",
                "label": "contains",
                "direction": "in",
                "source_node_id": "csharp:type:Sample.Downloader",
                "target_node_id": self.method_symbol["id"],
                "other": {
                    "node_id": "csharp:type:Sample.Downloader",
                    "kind": "Class",
                    "name": "Downloader",
                    "file_path": "Downloader.cs",
                    "start_line": 4,
                    "end_line": 32,
                },
            },
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
            },
            {
                "kind": "Invokes",
                "label": "calls",
                "direction": "out",
                "source_node_id": self.method_symbol["id"],
                "target_node_id": "csharp:method:Sample.Downloader.Normalize(System.String)",
                "other": {
                    "node_id": "csharp:method:Sample.Downloader.Normalize(System.String)",
                    "kind": "Method",
                    "name": "Normalize",
                    "file_path": "Downloader.cs",
                    "start_line": 26,
                    "end_line": 28,
                },
            },
            {
                "kind": "Invokes",
                "label": "calls",
                "direction": "in",
                "source_node_id": "csharp:method:Sample.Program.Main(System.String[])",
                "target_node_id": self.method_symbol["id"],
                "other": {
                    "node_id": "csharp:method:Sample.Program.Main(System.String[])",
                    "kind": "Method",
                    "name": "Main",
                    "file_path": "Program.cs",
                    "start_line": 8,
                    "end_line": 16,
                },
            },
            {
                "kind": "Reads",
                "label": "reads",
                "direction": "out",
                "source_node_id": self.method_symbol["id"],
                "target_node_id": "csharp:field:Sample.Downloader._client",
                "other": {
                    "node_id": "csharp:field:Sample.Downloader._client",
                    "kind": "Field",
                    "name": "_client",
                    "file_path": "Downloader.cs",
                    "start_line": 6,
                    "end_line": 6,
                },
            },
            {
                "kind": "Writes",
                "label": "writes",
                "direction": "out",
                "source_node_id": self.method_symbol["id"],
                "target_node_id": "csharp:property:Sample.Downloader.LastUrl",
                "other": {
                    "node_id": "csharp:property:Sample.Downloader.LastUrl",
                    "kind": "Property",
                    "name": "LastUrl",
                    "file_path": "Downloader.cs",
                    "start_line": 7,
                    "end_line": 7,
                },
            },
        ]

        return _prioritize_context_relationships(relationships, limit, group_limits)

    async def _search_lexical_context(self, query: ContextQuery) -> list[ContextHit]:
        return [
            await self._build_context_hit(
                self.method_symbol,
                0.5,
                query.repository_id,
                raw_score_name="lexical_score",
                expand_context=query.expand_context,
                context_depth=query.context_depth,
                include_context_relationships=query.include_context_relationships,
                context_relationship_limit=query.context_relationship_limit,
            )
        ]

    async def _get_content(self, content_hash: str) -> dict[str, object] | None:
        contents = {
            "method-body": {
                "hash": "method-body",
                "text": "public Task DownloadAsync(string url) { return Task.CompletedTask; }",
                "media_type": "text/x-csharp-fragment",
            }
        }
        return contents.get(content_hash)

    async def _get_node_summary(
        self,
        repository_id: str | None,
        node_id: str,
        content_hash: str | None = None,
    ) -> dict[str, object] | None:
        if repository_id != "repo:test" or node_id != self.method_symbol["id"]:
            return None

        return {
            "id": "summary:test",
            "repository_id": "repo:test",
            "node_id": self.method_symbol["id"],
            "content_hash": "method-body",
            "summary_kind": "symbol",
            "summary": "Downloads subtitles for a video URL.",
            "tags": ["download", "subtitles"],
            "confidence": "high",
            "provider": "test",
            "model": "summary-counting",
            "prompt_version": "node-summary-v1",
        }

    async def _search_summary_context(self, query: ContextQuery) -> list[ContextHit]:
        if not self.enable_summary_search:
            return []

        summary = await self._get_node_summary(
            query.repository_id, self.method_symbol["id"], "method-body"
        )
        if summary is None:
            return []

        return [
            await self._build_context_hit(
                self.method_symbol,
                0.72,
                query.repository_id,
                raw_score_name="summary_score",
                preview=str(summary["summary"]),
                expand_context=query.expand_context,
                context_depth=query.context_depth,
                include_context_relationships=query.include_context_relationships,
                context_relationship_limit=query.context_relationship_limit,
            )
        ]

    async def get_repository(self, repository_id: str) -> RepositorySummary | None:
        if repository_id not in {"repo:test", "sample_repo"}:
            return None

        return RepositorySummary(
            repository_id="repo:test",
            alias="sample_repo",
            root_path="C:/sample",
            last_run_id="run:test",
            last_stage="Completed",
            node_count=4,
            relationship_count=1,
            content_count=1,
            embedding_count=1,
        )

    async def list_ingestion_runs(
        self,
        repository_id: str | None = None,
        limit: int = 50,
    ) -> IngestionRunListResponse:
        if repository_id != "repo:test":
            return IngestionRunListResponse()

        return IngestionRunListResponse(
            runs=[
                IngestionRunSummary(
                    run_id="run:test",
                    repository_id="repo:test",
                    repository_root="C:/sample",
                    stage="Completed",
                    language="csharp",
                    parser_name="fake",
                    embedding_provider="test",
                    embedding_model="test",
                )
            ]
        )


class FakeVectorClient:
    def __init__(self, store: FakeReadStore) -> None:
        self._store = store

    async def health(self) -> dict[str, object]:
        return {"status": "healthy"}

    async def search(
        self,
        vector: list[float],
        limit: int,
        filters: dict[str, str],
    ) -> list[dict[str, object]]:
        if not any(vector):
            return []

        return [
            {
                "nodeId": self._store.parameter_declaration["id"],
                "contentHash": self._store.parameter_declaration["contentHash"],
                "repositoryId": "repo:test",
                "score": 0.6,
                "preview": "string url",
            }
        ]


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


def _relationship(
    kind: str,
    direction: str,
    name: str,
    start_line: int,
) -> dict[str, object]:
    return {
        "kind": kind,
        "label": kind.casefold(),
        "direction": direction,
        "source_node_id": f"source:{name}",
        "target_node_id": f"target:{name}",
        "other": {
            "node_id": f"node:{name}",
            "kind": "Method",
            "name": name,
            "file_path": "Sample.cs",
            "start_line": start_line,
            "end_line": start_line + 1,
        },
    }
