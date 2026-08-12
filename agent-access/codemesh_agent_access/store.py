from __future__ import annotations

import asyncio
import json
import os
import subprocess
from typing import Any

from .config import Settings
from .content_store import MongoContentStore, PyMongoError
from .embeddings import QueryEmbeddingProvider
from .graph_store import Neo4jGraphStore, lexical_terms
from .models import (
    ContextHit,
    ContextPackageItem,
    ContextPackageQuery,
    ContextPackageResponse,
    ContextQuery,
    ContextResponse,
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
    SymbolSearchHit,
    SymbolSearchResponse,
)
from .summary_store import MongoNodeSummaryStore
from .vector_store import QdrantSearchClient


_PREFERRED_CONTEXT_KINDS = {
    "method",
    "constructor",
    "class",
    "interface",
    "struct",
    "enum",
    "delegate",
    "property",
    "field",
    "event",
    "file",
    "testfile",
    "testcase",
    "document",
    "section",
}

_DECLARABLE_SYMBOL_KINDS = {
    "class",
    "interface",
    "struct",
    "enum",
    "delegate",
    "method",
    "testcase",
    "constructor",
    "property",
    "field",
    "event",
}

_SYMBOL_KINDS = _DECLARABLE_SYMBOL_KINDS | {
    "namespace",
    "parameter",
    "lambda",
}

_LOW_SIGNAL_KINDS = {
    "declaration",
    "parameter",
    "lambda",
    "namespace",
    "unknown",
}

_KIND_WEIGHTS = {
    "method": 1.30,
    "constructor": 1.28,
    "class": 1.22,
    "interface": 1.18,
    "struct": 1.16,
    "enum": 1.12,
    "delegate": 1.10,
    "file": 1.04,
    "testfile": 1.08,
    "testcase": 1.26,
    "document": 1.08,
    "section": 1.12,
    "property": 1.02,
    "field": 0.95,
    "event": 0.95,
    "namespace": 0.78,
    "declaration": 0.58,
    "parameter": 0.42,
    "lambda": 0.70,
    "unknown": 0.40,
}


class CodeMeshReadStore:
    """Read-side facade for graph, content, and vector intelligence."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._content = MongoContentStore(settings)
        self._summaries = MongoNodeSummaryStore(settings)
        self._embeddings = QueryEmbeddingProvider(settings)
        self._graph = Neo4jGraphStore(settings)
        self._vectors = QdrantSearchClient(settings)

    async def close(self) -> None:
        await self._graph.close()
        await self._content.close()
        summaries = getattr(self, "_summaries", None)
        if summaries is not None:
            await summaries.close()

    async def health(self) -> HealthResponse:
        components = {
            "neo4j": await self._graph.health(),
            "mongodb": await self._content.health(),
            "node_summaries": await self._summaries.health(),
            "qdrant": await self._vectors.health(),
            "model_provider": await self._embeddings.health(),
        }
        status = (
            "healthy"
            if all(_component_ok(value) for value in components.values())
            else "degraded"
        )
        return HealthResponse(status=status, components=components)

    async def search_context(self, query: ContextQuery) -> ContextResponse:
        query = await self._resolve_context_query_repository(query)
        vector = query.vector
        embedding_attempted = False
        embedding_source = "provided" if vector else "none"
        if not vector and self._embeddings.is_enabled and query.query.strip():
            embedding_attempted = True
            vector = await self._embeddings.embed_query(query.query)
            if vector:
                embedding_source = "model_provider"

        vector_task = (
            asyncio.create_task(self._search_vector_context(query, vector))
            if vector
            else None
        )
        lexical_task = (
            asyncio.create_task(self._search_lexical_context(query))
            if query.query.strip()
            else None
        )
        summary_task = (
            asyncio.create_task(self._search_summary_context(query))
            if query.query.strip()
            else None
        )
        vector_hits = await vector_task if vector_task else []
        lexical_hits = await lexical_task if lexical_task else []
        summary_hits = await summary_task if summary_task else []
        hits = [*vector_hits, *lexical_hits, *summary_hits]

        ranked_hits = _ranked_unique_hits(hits, query.limit)
        vector_hit_count = _source_hit_count(ranked_hits, "vector_score")
        lexical_hit_count = _source_hit_count(ranked_hits, "lexical_score")
        summary_hit_count = _source_hit_count(ranked_hits, "summary_score")
        diagnostics = {
            "mode": _search_mode(
                vector_hit_count, lexical_hit_count, summary_hit_count
            ),
            "embedding_attempted": embedding_attempted,
            "embedding_source": embedding_source,
            "model_provider": self._embeddings.provider,
            "vector_available": bool(vector),
            "vector_hit_count": vector_hit_count,
            "lexical_hit_count": lexical_hit_count,
            "summary_hit_count": summary_hit_count,
            "vector_candidate_count": len(vector_hits),
            "lexical_candidate_count": len(lexical_hits),
            "summary_candidate_count": len(summary_hits),
            "lexical_fallback": bool(vector) and not vector_hits,
            "hit_count": len(ranked_hits),
            "selected_snapshot_id": query.repository_id,
            "selected_project_id": next(
                (hit.repository_id for hit in ranked_hits if hit.repository_id), None
            ),
        }

        return ContextResponse(query=query, hits=ranked_hits, diagnostics=diagnostics)

    async def get_context_package(
        self, query: ContextPackageQuery
    ) -> ContextPackageResponse:
        requested_repository_id = query.repository_id
        query = await self._resolve_package_query_repository(query)
        search = await self.search_context(
            ContextQuery(
                query=query.query,
                repository_id=query.repository_id,
                limit=query.limit,
                kinds=query.kinds,
                filters=query.filters,
                vector=query.vector,
                expand_context=True,
                context_depth=query.context_depth,
                include_context_relationships=False,
            )
        )
        repository_summary = None
        repository = None
        latest_run = None
        if requested_repository_id:
            repository_summary = await self.get_repository(requested_repository_id)
            if query.include_repository:
                repository = (
                    repository_summary.model_dump(mode="json")
                    if repository_summary
                    else None
                )
        if query.include_repository and requested_repository_id:
            runs = await self.list_ingestion_runs(
                repository_id=(
                    repository_summary.repository_id
                    if repository_summary
                    else requested_repository_id
                ),
                limit=1,
            )
            latest_run = runs.runs[0].model_dump(mode="json") if runs.runs else None

        max_characters = max(0, query.max_characters)
        remaining_characters = max_characters
        items: list[ContextPackageItem] = []
        total_snippet_characters = 0

        for index, hit in enumerate(search.hits):
            repository_id = hit.snapshot_id or query.repository_id
            node_response = await self.get_node(
                NodeLookup(
                    node_id=hit.node_id,
                    repository_id=repository_id,
                    include_content=query.include_content,
                    include_neighbors=False,
                )
            )
            content = _content_metadata(node_response.content)
            snippet = None
            content_document = node_response.content
            if query.include_content and hit.content_hash:
                if (
                    content_document is None
                    or str(content_document.get("hash") or "") != hit.content_hash
                ):
                    content_document = await self._get_content(hit.content_hash)
                content = _content_metadata(content_document)

            if query.include_content and content_document and remaining_characters > 0:
                remaining_items = max(1, len(search.hits) - index)
                item_budget = max(0, remaining_characters // remaining_items)
                snippet = _snippet_for_hit(content_document, hit, item_budget)
                total_snippet_characters += len(snippet or "")
                remaining_characters = max(0, remaining_characters - len(snippet or ""))

            summary = await self._get_node_summary(
                repository_id, hit.node_id, hit.content_hash
            )

            relationships = []
            if query.include_relationships:
                relationships = await self._get_context_relationship_summaries(
                    hit.node_id,
                    repository_id,
                    query.relationship_limit,
                    _relationship_group_limits(query),
                )

            items.append(
                ContextPackageItem(
                    hit=hit,
                    node=node_response.node,
                    content=content,
                    summary=summary,
                    snippet=snippet,
                    relationships=relationships,
                    relationship_groups=_group_relationships(relationships),
                    rationale={
                        "rank": index + 1,
                        "score": hit.score,
                        "score_components": hit.score_components,
                        "expanded": hit.expanded_context is not None,
                    },
                )
            )

        return ContextPackageResponse(
            query=query,
            repository=repository,
            latest_run=latest_run,
            items=items,
            validation_recommendations=_validation_recommendations(
                items, repository_summary
            ),
            total_snippet_characters=total_snippet_characters,
        )

    async def search_symbols(self, query: SymbolQuery) -> SymbolSearchResponse:
        query = await self._resolve_symbol_query_repository(query)
        nodes = await self._search_symbol_nodes(query)
        search_text = query.query.casefold()

        filtered_nodes = [
            node
            for node in nodes
            if _matches_filters(node, query.filters)
            and _matches_repository(node, query.repository_id)
        ]
        scored_nodes = sorted(
            (
                (
                    node,
                    _symbol_score(node, search_text),
                    _symbol_score_components(node, search_text),
                )
                for node in filtered_nodes
            ),
            key=lambda item: (
                item[1],
                _kind_weight(item[0]),
                -_int(item[0].get("startLine")),
            ),
            reverse=True,
        )

        symbols: list[SymbolSearchHit] = []
        for node, score, score_components in scored_nodes[: max(0, query.limit)]:
            declaration = None
            if query.include_declarations:
                declaration_node = await self._get_primary_declaration_node(
                    node, query.repository_id
                )
                declaration = (
                    _normalize_node(declaration_node) if declaration_node else None
                )

            symbols.append(
                SymbolSearchHit(
                    node=_normalize_node(node),
                    declaration=declaration,
                    score=score,
                    score_components=score_components,
                )
            )

        return SymbolSearchResponse(query=query, symbols=symbols)

    async def get_node(self, lookup: NodeLookup) -> NodeResponse:
        lookup = await self._resolve_node_lookup_repository(lookup)
        node = await self._get_node_properties(lookup.node_id, lookup.repository_id)
        if node is None or not _matches_repository(node, lookup.repository_id):
            return NodeResponse()

        normalized_node = _normalize_node(node)
        content = None
        relationships: list[dict[str, Any]] = []

        if lookup.include_content:
            content_hash = str(node.get("contentHash") or "")
            content = await self._get_content(content_hash)

        if lookup.include_neighbors:
            relationships = await self._get_relationships(
                lookup.node_id, lookup.repository_id, depth=1
            )

        return NodeResponse(
            node=normalized_node, content=content, relationships=relationships
        )

    async def get_neighbors(self, query: NeighborQuery) -> NodeResponse:
        query = await self._resolve_neighbor_query_repository(query)
        relationships = await self._get_relationships(
            query.node_id, query.repository_id, query.depth, query.relationship_kinds
        )
        return NodeResponse(relationships=relationships)

    async def list_repositories(self, limit: int = 50) -> RepositoryListResponse:
        return await self._content.list_repositories(limit)

    async def get_repository(self, repository_id: str) -> RepositorySummary | None:
        return await self._content.get_repository(repository_id)

    async def delete_repository(self, repository_id: str) -> RepositoryDeleteResponse:
        repository = await self.get_repository(repository_id)
        if repository is None:
            return RepositoryDeleteResponse(repository_id=repository_id)

        resolved_repository_id = repository.repository_id
        list_snapshot_ids = getattr(self._content, "list_snapshot_ids", None)
        snapshot_ids = (
            await list_snapshot_ids(resolved_repository_id)
            if list_snapshot_ids is not None
            else []
        )
        namespace_ids = list(dict.fromkeys([resolved_repository_id, *snapshot_ids]))
        graph_cleaned = content_cleaned = embeddings_cleaned = summaries_cleaned = False

        for namespace_id in namespace_ids:
            await self._graph.delete_repository(namespace_id)
        graph_cleaned = True

        await self._content.delete_repository(resolved_repository_id)
        content_cleaned = True

        for namespace_id in namespace_ids:
            await self._vectors.delete_repository(namespace_id)
        embeddings_cleaned = True

        for namespace_id in namespace_ids:
            await self._summaries.delete_repository(namespace_id)
        summaries_cleaned = True

        return RepositoryDeleteResponse(
            repository_id=resolved_repository_id,
            deleted=True,
            registry_entry_existed=True,
            graph_cleaned=graph_cleaned,
            content_cleaned=content_cleaned,
            embeddings_cleaned=embeddings_cleaned,
            summaries_cleaned=summaries_cleaned,
        )

    async def get_summary_coverage(
        self, repository_id: str
    ) -> NodeSummaryCoverageResponse:
        resolved_repository_id = await self._resolve_repository_id(repository_id)
        coverage = await self._summaries.summary_coverage(
            resolved_repository_id or repository_id
        )
        return NodeSummaryCoverageResponse(**coverage)

    async def list_ingestion_runs(
        self,
        repository_id: str | None = None,
        limit: int = 50,
    ) -> IngestionRunListResponse:
        return await self._content.list_ingestion_runs(repository_id, limit)

    async def get_repository_status(
        self, repository_id: str
    ) -> RepositoryStatusResponse:
        repository = await self.get_repository(repository_id)
        if repository is None:
            return RepositoryStatusResponse(
                repository_id=repository_id,
                freshness={
                    "status": "missing",
                    "is_stale": None,
                    "detail": "Repository was not found in the CodeMesh registry.",
                },
                refresh=_refresh_status(None),
            )

        runs = await self.list_ingestion_runs(repository.repository_id, limit=1)
        latest_run = runs.runs[0] if runs.runs else None
        summary_coverage = await self.get_summary_coverage(repository.repository_id)
        freshness = await asyncio.to_thread(_repository_freshness, repository)

        return RepositoryStatusResponse(
            repository_id=repository.repository_id,
            repository=repository,
            latest_run=latest_run,
            summary_coverage=summary_coverage,
            counts={
                "graph_nodes": repository.node_count,
                "relationships": repository.relationship_count,
                "content_documents": repository.content_count,
                "vectors": repository.embedding_count,
                "summaries_total": summary_coverage.total_count,
                "summaries_completed": summary_coverage.completed_count,
                "summaries_failed": summary_coverage.failed_count,
            },
            freshness=freshness,
            refresh=_refresh_status(latest_run, freshness),
        )

    async def _resolve_context_query_repository(
        self, query: ContextQuery
    ) -> ContextQuery:
        repository_id = await self._resolve_repository_id(query.repository_id)
        return (
            query
            if repository_id == query.repository_id
            else query.model_copy(update={"repository_id": repository_id})
        )

    async def _resolve_package_query_repository(
        self, query: ContextPackageQuery
    ) -> ContextPackageQuery:
        repository_id = await self._resolve_repository_id(query.repository_id)
        return (
            query
            if repository_id == query.repository_id
            else query.model_copy(update={"repository_id": repository_id})
        )

    async def _resolve_symbol_query_repository(self, query: SymbolQuery) -> SymbolQuery:
        repository_id = await self._resolve_repository_id(query.repository_id)
        return (
            query
            if repository_id == query.repository_id
            else query.model_copy(update={"repository_id": repository_id})
        )

    async def _resolve_node_lookup_repository(self, lookup: NodeLookup) -> NodeLookup:
        repository_id = await self._resolve_repository_id(lookup.repository_id)
        return (
            lookup
            if repository_id == lookup.repository_id
            else lookup.model_copy(update={"repository_id": repository_id})
        )

    async def _resolve_neighbor_query_repository(
        self, query: NeighborQuery
    ) -> NeighborQuery:
        repository_id = await self._resolve_repository_id(query.repository_id)
        return (
            query
            if repository_id == query.repository_id
            else query.model_copy(update={"repository_id": repository_id})
        )

    async def _resolve_repository_id(self, repository_id: str | None) -> str | None:
        if not repository_id:
            return None

        try:
            repository = await self.get_repository(repository_id)
        except PyMongoError:
            return repository_id

        if repository:
            return (
                repository.snapshot_id
                or repository.metadata.get("snapshotId")
                or repository.repository_id
            )

        resolver = getattr(self._content, "resolve_snapshot_id", None)
        if resolver is not None:
            resolved = await resolver(repository_id)
            if resolved:
                return resolved

        return repository_id

    async def _get_node_properties(
        self, node_id: str, repository_id: str | None = None
    ) -> dict[str, Any] | None:
        return await self._graph.get_node_properties(node_id, repository_id)

    async def _search_symbol_nodes(self, query: SymbolQuery) -> list[dict[str, Any]]:
        search_text = query.query.casefold()
        kinds = _symbol_kind_filter(query.kinds)
        if not kinds:
            return []

        limit = min(max(query.limit * 4, 24), 300)
        return await self._graph.search_symbol_nodes(
            search_text, kinds, query.repository_id, limit
        )

    async def _get_relationships(
        self,
        node_id: str,
        repository_id: str | None = None,
        depth: int = 1,
        relationship_kinds: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        kinds = {kind.casefold() for kind in relationship_kinds or []}
        records = await self._graph.get_relationship_properties(
            node_id, repository_id, depth
        )
        relationships = [_normalize_relationship(record) for record in records]
        if not kinds:
            return relationships

        return [
            item
            for item in relationships
            if str(item.get("kind", "")).casefold() in kinds
        ]

    async def _get_context_candidates(
        self,
        node_id: str,
        repository_id: str | None = None,
        depth: int = 4,
    ) -> list[dict[str, Any]]:
        return await self._graph.get_context_candidates(node_id, repository_id, depth)

    async def _get_primary_declaration_node(
        self,
        node: dict[str, Any],
        repository_id: str | None = None,
    ) -> dict[str, Any] | None:
        if _kind(node) not in _DECLARABLE_SYMBOL_KINDS:
            return None

        node_id = str(node.get("id") or "")
        if not node_id:
            return None

        return await self._graph.get_primary_declaration_node(node_id, repository_id)

    async def _get_context_relationship_summaries(
        self,
        node_id: str,
        repository_id: str | None = None,
        limit: int = 8,
        group_limits: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        clamped_limit = min(max(limit, 1), 50)
        selection_limit = min(max(clamped_limit * 8, 80), 500)
        records = await self._graph.get_context_relationship_records(
            node_id, repository_id, selection_limit
        )

        summaries = []
        for record in records:
            relationship = dict(record["relationship"])
            other = dict(record["other"])
            source_node_id = str(relationship.get("sourceNodeId") or "")
            target_node_id = str(relationship.get("targetNodeId") or "")
            summaries.append(
                {
                    "kind": str(relationship.get("kind") or ""),
                    "label": relationship.get("label"),
                    "direction": "out" if source_node_id == node_id else "in",
                    "source_node_id": source_node_id,
                    "target_node_id": target_node_id,
                    "other": _context_ref(other),
                }
            )

        return _prioritize_context_relationships(summaries, clamped_limit, group_limits)

    async def _get_content(self, content_hash: str) -> dict[str, Any] | None:
        return await self._content.get_content(content_hash)

    async def _get_node_summary(
        self,
        repository_id: str | None,
        node_id: str,
        content_hash: str | None = None,
    ) -> dict[str, Any] | None:
        return await self._summaries.get_node_summary(
            repository_id, node_id, content_hash
        )

    async def _select_context_node(
        self,
        node: dict[str, Any],
        repository_id: str | None = None,
        expand_context: bool = True,
        context_depth: int = 4,
    ) -> tuple[dict[str, Any], str]:
        node_id = str(node.get("id") or "")
        if not node_id:
            return node, "self"

        if not expand_context:
            return node, "self"

        candidates = await self._get_context_candidates(
            node_id, repository_id, context_depth
        )
        if not _needs_context_expansion(node) and not candidates:
            return node, "self"

        best = _choose_context_candidate(node, candidates)
        if best is None:
            return node, "self"

        return best["node"], str(best.get("reason") or "context")

    async def _build_context_hit(
        self,
        node: dict[str, Any],
        raw_score: float,
        repository_id: str | None = None,
        raw_score_name: str = "raw",
        preview: str | None = None,
        source_node: dict[str, Any] | None = None,
        expand_context: bool = True,
        context_depth: int = 4,
        include_context_relationships: bool = False,
        context_relationship_limit: int = 8,
    ) -> ContextHit:
        source = source_node or node
        selected, expansion_reason = await self._select_context_node(
            node,
            repository_id,
            expand_context,
            context_depth,
        )
        declaration = await self._get_primary_declaration_node(selected, repository_id)

        content_node = declaration or selected
        content_hash = str(
            content_node.get("contentHash")
            or selected.get("contentHash")
            or source.get("contentHash")
            or ""
        )
        content = await self._get_content(content_hash)
        selected_id = str(selected.get("id") or "")
        source_id = str(source.get("id") or "")
        declaration_id = str(declaration.get("id") or "") if declaration else ""
        selected_own_preview = (
            preview if selected_id == source_id and not declaration else None
        )
        kind_weight = _kind_weight(selected)
        expansion_bonus = _expansion_bonus(source, selected, declaration)
        adjusted_score = _adjust_score(raw_score, kind_weight, expansion_bonus)

        expanded_context = None
        if selected_id != source_id or declaration_id:
            expanded_context = {
                "reason": expansion_reason,
                "source": _context_ref(source),
                "selected": _context_ref(selected),
                "declaration": _context_ref(declaration) if declaration else None,
            }

        if include_context_relationships:
            relationships = await self._get_context_relationship_summaries(
                selected_id,
                repository_id,
                context_relationship_limit,
            )
            if expanded_context is None:
                expanded_context = {
                    "reason": expansion_reason,
                    "source": _context_ref(source),
                    "selected": _context_ref(selected),
                    "declaration": _context_ref(declaration) if declaration else None,
                }
            expanded_context["relationships"] = relationships

        return _context_hit_for_node(
            selected,
            adjusted_score,
            content,
            selected_own_preview,
            span_node=declaration or selected,
            score_components={
                raw_score_name: raw_score,
                "kind_weight": kind_weight,
                "expansion_bonus": expansion_bonus,
            },
            expanded_context=expanded_context,
        )

    async def _search_lexical_context(self, query: ContextQuery) -> list[ContextHit]:
        search_text = query.query.casefold()
        kinds = [kind.casefold() for kind in query.kinds]
        candidate_limit = min(max(query.limit * 4, 16), 200)
        raw_limit = min(max(query.limit * 16, 64), 500)
        repository_id = query.repository_id

        nodes = await self._graph.search_context_nodes(
            search_text, kinds, repository_id, raw_limit
        )
        nodes = [
            node
            for node in nodes
            if _matches_filters(node, query.filters)
            and _matches_repository(node, query.repository_id)
        ]
        nodes.sort(key=lambda node: _lexical_score(node, search_text), reverse=True)
        nodes = _diversify_lexical_nodes(nodes, candidate_limit)

        hits = []
        for node in nodes:
            hits.append(
                await self._build_context_hit(
                    node,
                    _lexical_score(node, search_text),
                    query.repository_id,
                    raw_score_name="lexical_score",
                    expand_context=query.expand_context,
                    context_depth=query.context_depth,
                    include_context_relationships=query.include_context_relationships,
                    context_relationship_limit=query.context_relationship_limit,
                )
            )

        return hits

    async def _search_vector_context(
        self, query: ContextQuery, vector: list[float]
    ) -> list[ContextHit]:
        qdrant_hits = await self._vectors.search(
            vector, _candidate_limit(query.limit), _effective_filters(query)
        )
        hits: list[ContextHit] = []

        for item in qdrant_hits:
            node_id = str(item.get("nodeId") or "")
            content_hash = str(item.get("contentHash") or "")
            repository_id = (
                query.repository_id or str(item.get("repositoryId") or "") or None
            )
            node = await self._get_node_properties(node_id, repository_id)

            if node is None:
                node = {
                    "id": node_id,
                    "stableKey": node_id,
                    "kind": "Unknown",
                    "name": node_id,
                    "filePath": "",
                    "startLine": 0,
                    "endLine": 0,
                    "contentHash": content_hash,
                }

            preview = str(item.get("preview") or "") or None
            hits.append(
                await self._build_context_hit(
                    node,
                    float(item.get("score") or 0),
                    repository_id,
                    raw_score_name="vector_score",
                    preview=preview,
                    expand_context=query.expand_context,
                    context_depth=query.context_depth,
                    include_context_relationships=query.include_context_relationships,
                    context_relationship_limit=query.context_relationship_limit,
                )
            )

        return hits

    async def _search_summary_context(self, query: ContextQuery) -> list[ContextHit]:
        search_text = query.query.casefold()
        kinds = [kind for kind in query.kinds if kind]
        summaries = await self._summaries.search_summaries(
            query.query,
            query.repository_id,
            kinds,
            _candidate_limit(query.limit),
        )
        hits: list[ContextHit] = []

        for summary in summaries:
            node_id = str(summary.get("node_id") or "")
            if not node_id:
                continue

            repository_id = (
                query.repository_id or str(summary.get("repository_id") or "") or None
            )
            node = await self._get_node_properties(node_id, repository_id)
            if node is None:
                node = _node_from_summary(summary)

            if not _matches_filters(node, query.filters) or not _matches_repository(
                node, query.repository_id
            ):
                continue

            hits.append(
                await self._build_context_hit(
                    node,
                    _summary_score(summary, search_text),
                    repository_id,
                    raw_score_name="summary_score",
                    preview=str(summary.get("summary") or "") or None,
                    expand_context=query.expand_context,
                    context_depth=query.context_depth,
                    include_context_relationships=query.include_context_relationships,
                    context_relationship_limit=query.context_relationship_limit,
                )
            )

        return hits


def _component_ok(component: Any) -> bool:
    return isinstance(component, dict) and component.get("status") in {
        "healthy",
        "configured",
    }


def _repository_freshness(repository: RepositorySummary) -> dict[str, Any]:
    indexed_commit = (
        repository.commit
        or repository.metadata.get("commit")
        or repository.metadata.get("repositoryCommit")
    )
    root_path = repository.root_path
    selected_snapshot_id = repository.snapshot_id or repository.metadata.get(
        "snapshotId"
    )
    observed_snapshot_id = repository.metadata.get("observedSnapshotId")
    git = _git_snapshot(root_path)

    if git["available"]:
        current_commit = git.get("current_commit")
        is_dirty = bool(git.get("working_tree_dirty"))
        commit_mismatch = bool(indexed_commit and indexed_commit != current_commit)
        source_view_mismatch = (
            observed_snapshot_id != selected_snapshot_id
            if observed_snapshot_id and selected_snapshot_id
            else None
        )
        if indexed_commit:
            is_stale = commit_mismatch or is_dirty or source_view_mismatch is True
            status = "stale" if is_stale else "fresh"
            detail = (
                "Indexed commit differs from the local checkout or the working tree has uncommitted changes."
                if is_stale
                else "Indexed commit matches the local checkout and the working tree is clean."
            )
        else:
            is_stale = None
            status = "unknown"
            detail = "The registry does not include an indexed commit yet; run-level commit stamping is not available."

        return {
            **git,
            "indexed_commit": indexed_commit,
            "selected_snapshot_id": selected_snapshot_id,
            "indexed_source_view_hash": repository.source_view_hash
            or repository.metadata.get("sourceViewHash"),
            "commit_mismatch": commit_mismatch,
            "source_view_mismatch": source_view_mismatch,
            "provenance_status": "known" if selected_snapshot_id else "unknown",
            "is_stale": is_stale,
            "status": status,
            "detail": detail,
        }

    return {
        **git,
        "indexed_commit": indexed_commit,
        "selected_snapshot_id": selected_snapshot_id,
        "indexed_source_view_hash": repository.source_view_hash
        or repository.metadata.get("sourceViewHash"),
        "commit_mismatch": None,
        "source_view_mismatch": None,
        "provenance_status": "unavailable",
        "is_stale": None,
        "status": "unknown",
        "detail": git.get("detail")
        or "Local git state is unavailable for this repository path.",
    }


def _git_snapshot(root_path: str) -> dict[str, Any]:
    if not root_path or not os.path.isdir(root_path):
        return {
            "available": False,
            "root_path": root_path,
            "detail": "Repository root path is not accessible from Agent Access.",
        }

    current_commit = _run_git(root_path, "rev-parse", "HEAD")
    if current_commit is None:
        return {
            "available": False,
            "root_path": root_path,
            "detail": "Repository root is not a readable git checkout.",
        }

    branch = _run_git(root_path, "rev-parse", "--abbrev-ref", "HEAD")
    status = _run_git(root_path, "status", "--porcelain")
    return {
        "available": True,
        "root_path": root_path,
        "current_commit": current_commit,
        "current_branch": branch,
        "working_tree_dirty": bool(status),
    }


def _run_git(root_path: str, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", root_path, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    return result.stdout.strip()


def _refresh_status(
    latest_run: Any | None, freshness: dict[str, Any] | None = None
) -> dict[str, Any]:
    if latest_run is None:
        return {
            "status": "no_run",
            "is_running": False,
            "changed": None,
            "latest_run_id": None,
            "detail": "No ingestion run is available for this repository.",
            "recommended_action": "Run `codemesh refresh` for the repository.",
        }

    stage = str(getattr(latest_run, "stage", "") or "")
    stage_key = stage.casefold()
    stats = getattr(latest_run, "stats", None) or {}
    changed = _refresh_changed(stats)
    is_stale = (freshness or {}).get("is_stale")

    if stage_key in {"accepted", "parsing", "persisting", "embedding"}:
        status = "running"
        detail = "A repository ingestion run is currently in progress."
    elif (
        stage_key == "failed"
        or int(getattr(latest_run, "error_diagnostic_count", 0)) > 0
    ):
        status = "failed"
        detail = (
            "The latest repository ingestion run failed or emitted error diagnostics."
        )
    elif bool(getattr(latest_run, "dry_run", False)):
        status = "dry_run"
        detail = "The latest run was a dry run and did not update persisted context."
    elif stage_key == "completed" and changed is False:
        status = "skipped"
        detail = "The latest refresh found no persisted graph, content, vector, or summary changes."
    elif stage_key == "completed":
        status = "completed"
        detail = "The latest refresh completed and updated persisted context."
    else:
        status = "unknown"
        detail = (
            "The latest repository ingestion stage is not recognized by Agent Access."
        )

    recommended_action = "None."
    if status in {"no_run", "failed", "dry_run", "unknown"}:
        recommended_action = "Run `codemesh refresh` and inspect recent ingestion runs."
    elif is_stale is True:
        recommended_action = (
            "Run `codemesh refresh`; local git freshness indicates stale context."
        )

    return {
        "status": status,
        "is_running": status == "running",
        "changed": changed,
        "latest_run_id": getattr(latest_run, "run_id", None),
        "stage": stage or None,
        "started_at": getattr(latest_run, "started_at", None),
        "finished_at": getattr(latest_run, "finished_at", None),
        "message": getattr(latest_run, "message", None),
        "dry_run": bool(getattr(latest_run, "dry_run", False)),
        "skip_embeddings": bool(getattr(latest_run, "skip_embeddings", True)),
        "language": getattr(latest_run, "language", None),
        "parser_name": getattr(latest_run, "parser_name", None),
        "diagnostic_count": int(getattr(latest_run, "diagnostic_count", 0)),
        "error_diagnostic_count": int(getattr(latest_run, "error_diagnostic_count", 0)),
        "warning_diagnostic_count": int(
            getattr(latest_run, "warning_diagnostic_count", 0)
        ),
        "stats": stats,
        "detail": detail,
        "recommended_action": recommended_action,
    }


def _refresh_changed(stats: dict[str, Any]) -> bool | None:
    if not stats:
        return None

    write_keys = [
        "written_node_count",
        "written_relationship_count",
        "written_content_count",
        "written_embedding_count",
        "written_summary_count",
    ]
    parsed_keys = [
        "parsed_node_count",
        "parsed_relationship_count",
        "parsed_content_count",
        "summary_candidate_count",
    ]
    if any(_int(stats.get(key)) > 0 for key in write_keys):
        return True
    if any(_int(stats.get(key)) > 0 for key in parsed_keys):
        return False
    return None


def _validation_recommendations(
    items: list[ContextPackageItem],
    repository: RepositorySummary | None = None,
) -> list[dict[str, Any]]:
    file_paths = sorted(
        {_normalized_file_path(item) for item in items if _normalized_file_path(item)},
        key=str.casefold,
    )
    if not file_paths:
        return []

    recommendations: list[dict[str, Any]] = []
    is_codemesh = repository is not None and repository.alias == "code_mesh"

    if not is_codemesh:
        if any(_is_dotnet_path(path) for path in file_paths):
            recommendations.append(
                _validation_command(
                    "dotnet-build",
                    "dotnet build",
                    "Build the indexed .NET repository from its root. Inspect "
                    "repository-owned workflow and test configuration before "
                    "claiming broader validation.",
                    file_paths,
                )
            )
        return recommendations

    if any(_is_dotnet_path(path) for path in file_paths):
        recommendations.append(
            _validation_command(
                "dotnet-tests",
                "dotnet run --project tests/CodeMesh.Tests",
                "Run after .NET parser, ingestion, storage, CLI, or contract changes.",
                file_paths,
            )
        )

    if any(_is_agent_access_path(path) for path in file_paths):
        recommendations.append(
            _validation_command(
                "agent-access-tests",
                "cd agent-access; uv run pytest",
                "Run after Agent Access REST, MCP, CLI, ranking, formatting, or store read-path changes.",
                file_paths,
            )
        )
        recommendations.append(
            _validation_command(
                "agent-access-lint",
                "cd agent-access; uv run ruff check .; uv run ruff format --check .",
                "Run after Python Agent Access changes to verify linting and formatting.",
                file_paths,
            )
        )

    if any(_is_deployment_path(path) for path in file_paths):
        recommendations.append(
            _validation_command(
                "deployment-dry-run",
                "dotnet run --project src/CodeMesh.Cli -- ingest --root . --language deployment --dry-run --skip-embeddings",
                "Run after Dockerfile or Docker Compose changes to validate deployment artifact parsing.",
                file_paths,
            )
        )
        recommendations.append(
            _validation_command(
                "e2e-smoke",
                ".\\scripts\\e2e-smoke.ps1",
                "Run when changes affect Docker services, live store wiring, repository lifecycle, cleanup, REST, or Agent Access integration.",
                file_paths,
            )
        )

    if any(_is_markdown_path(path) for path in file_paths):
        recommendations.append(
            _validation_command(
                "markdown-dry-run",
                "dotnet run --project src/CodeMesh.Cli -- ingest --root . --language markdown --dry-run --skip-embeddings",
                "Run after documentation changes when Markdown ingestion shape matters.",
                file_paths,
            )
        )

    return recommendations


def _validation_command(
    identifier: str,
    command: str,
    reason: str,
    file_paths: list[str],
) -> dict[str, Any]:
    return {
        "id": identifier,
        "command": command,
        "reason": reason,
        "applies_to": [
            path for path in file_paths if _validation_applies(identifier, path)
        ][:8],
    }


def _validation_applies(identifier: str, path: str) -> bool:
    return (
        (identifier == "dotnet-tests" and _is_dotnet_path(path))
        or (identifier == "dotnet-build" and _is_dotnet_path(path))
        or (
            identifier in {"agent-access-tests", "agent-access-lint"}
            and _is_agent_access_path(path)
        )
        or (
            identifier in {"deployment-dry-run", "e2e-smoke"}
            and _is_deployment_path(path)
        )
        or (identifier == "markdown-dry-run" and _is_markdown_path(path))
    )


def _normalized_file_path(item: ContextPackageItem) -> str:
    file_path = item.hit.file_path
    if not file_path and item.node:
        span = item.node.get("span")
        if isinstance(span, dict):
            file_path = str(span.get("file_path") or "")

    return file_path.replace("\\", "/").strip()


def _is_dotnet_path(path: str) -> bool:
    lower = path.casefold()
    return lower.endswith((".cs", ".csproj", ".sln", ".slnx"))


def _is_agent_access_path(path: str) -> bool:
    lower = path.casefold()
    return lower.startswith("agent-access/") or lower.endswith(".py")


def _is_deployment_path(path: str) -> bool:
    lower = path.casefold()
    name = lower.rsplit("/", 1)[-1]
    return (
        name == "dockerfile"
        or name.endswith(".dockerfile")
        or name
        in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}
    )


def _is_markdown_path(path: str) -> bool:
    lower = path.casefold()
    return lower.endswith(".md") or lower.endswith(".markdown")


def _normalize_node(node: dict[str, Any]) -> dict[str, Any]:
    metadata = _metadata(node.get("metadataJson"))
    return {
        "storage_key": str(node.get("storageKey") or ""),
        "id": str(node.get("id") or ""),
        "stable_key": str(node.get("stableKey") or ""),
        "kind": str(node.get("kind") or ""),
        "name": str(node.get("name") or ""),
        "language": str(node.get("language") or ""),
        "project": str(node.get("project") or ""),
        "repository_id": str(
            metadata.get("projectId") or node.get("repositoryId") or ""
        ),
        "snapshot_id": str(
            metadata.get("snapshotId") or node.get("repositoryId") or ""
        ),
        "ingestion_run_id": str(node.get("ingestionRunId") or ""),
        "span": {
            "file_path": str(node.get("filePath") or ""),
            "start_line": _int(node.get("startLine")),
            "start_column": _int(node.get("startColumn")),
            "end_line": _int(node.get("endLine")),
            "end_column": _int(node.get("endColumn")),
        },
        "content_hash": str(node.get("contentHash") or ""),
        "metadata": metadata,
    }


def _normalize_relationship(relationship: dict[str, Any]) -> dict[str, Any]:
    return {
        "storage_key": str(relationship.get("storageKey") or ""),
        "id": str(relationship.get("id") or ""),
        "source_storage_key": str(relationship.get("sourceStorageKey") or ""),
        "source_node_id": str(relationship.get("sourceNodeId") or ""),
        "target_storage_key": str(relationship.get("targetStorageKey") or ""),
        "target_node_id": str(relationship.get("targetNodeId") or ""),
        "kind": str(relationship.get("kind") or ""),
        "label": relationship.get("label"),
        "metadata": _metadata(relationship.get("metadataJson")),
    }


def _content_metadata(content: dict[str, Any] | None) -> dict[str, Any] | None:
    if content is None:
        return None

    return {
        "hash": str(content.get("hash") or ""),
        "media_type": str(content.get("media_type") or ""),
        "created_at": content.get("created_at"),
        "updated_at": content.get("updated_at"),
    }


def _relationship_group_limits(query: ContextPackageQuery) -> dict[str, int]:
    values = {
        "callers": query.caller_limit,
        "callees": query.callee_limit,
        "reads": query.read_limit,
        "writes": query.write_limit,
        "contains": query.contains_limit,
        "defines": query.definition_limit,
        "uses_types": query.uses_type_limit,
    }

    return {
        name: max(0, min(int(value), 50))
        for name, value in values.items()
        if value is not None
    }


def _prioritize_context_relationships(
    relationships: list[dict[str, Any]],
    limit: int,
    group_limits: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    limits = group_limits or {}
    counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for relationship in sorted(relationships, key=_context_relationship_sort_key):
        group = _relationship_group_name(relationship)
        if group in limits:
            count = counts.get(group, 0)
            if count >= limits[group]:
                continue
            counts[group] = count + 1

        selected.append(relationship)
        if len(selected) >= limit:
            break

    return selected


def _context_relationship_sort_key(
    relationship: dict[str, Any],
) -> tuple[int, int, str, str, str]:
    other = relationship.get("other")
    if not isinstance(other, dict):
        other = {}

    start_line = _int(other.get("start_line"))
    line_sort = start_line if start_line > 0 else 1_000_000

    return (
        _context_relationship_priority(relationship),
        line_sort,
        str(other.get("kind") or "").casefold(),
        str(other.get("name") or "").casefold(),
        str(other.get("node_id") or "").casefold(),
    )


def _context_relationship_priority(relationship: dict[str, Any]) -> int:
    kind = str(relationship.get("kind") or "").casefold()
    direction = str(relationship.get("direction") or "").casefold()

    if kind == "defines":
        return 0
    if kind == "contains" and direction == "in":
        return 1
    if kind == "invokes" and direction == "in":
        return 2
    if kind == "invokes" and direction == "out":
        return 3
    if kind == "writes":
        return 4
    if kind == "reads":
        return 5
    if kind in {"usestype", "uses_type", "uses-type"}:
        return 6
    if kind == "returns":
        return 7
    if kind in {"inherits", "implements", "overrides"}:
        return 8
    if kind == "contains":
        return 9

    return 50


def _relationship_group_name(relationship: dict[str, Any]) -> str | None:
    kind = str(relationship.get("kind") or "").casefold()
    direction = str(relationship.get("direction") or "").casefold()

    if kind == "invokes":
        return "callees" if direction == "out" else "callers"
    if kind == "reads":
        return "reads"
    if kind == "writes":
        return "writes"
    if kind == "contains":
        return "contains"
    if kind == "defines":
        return "defines"
    if kind in {"usestype", "uses_type", "uses-type"}:
        return "uses_types"

    return None


def _group_relationships(
    relationships: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "callers": [],
        "callees": [],
        "reads": [],
        "writes": [],
        "contains": [],
        "defines": [],
        "uses_types": [],
    }

    for relationship in relationships:
        group = _relationship_group_name(relationship)
        if group in groups:
            groups[group].append(relationship)

    return groups


def _snippet_for_hit(
    content: dict[str, Any], hit: ContextHit, max_characters: int
) -> str | None:
    if max_characters <= 0:
        return None

    text = str(content.get("text") or "")
    if not text:
        return None

    lines = text.splitlines()
    if lines and 0 < hit.start_line <= hit.end_line <= len(lines):
        text = "\n".join(lines[hit.start_line - 1 : hit.end_line])

    return _trim_text(text, max_characters)


def _trim_text(text: str, max_characters: int) -> str:
    if len(text) <= max_characters:
        return text

    suffix = "\n...<trimmed>"
    if max_characters <= len(suffix):
        return text[:max_characters]

    return f"{text[: max_characters - len(suffix)].rstrip()}{suffix}"


def _context_ref(node: dict[str, Any] | None) -> dict[str, Any] | None:
    if node is None:
        return None

    normalized = _normalize_node(node)
    return {
        "node_id": normalized["id"],
        "kind": normalized["kind"],
        "name": normalized["name"],
        "file_path": normalized["span"]["file_path"],
        "start_line": normalized["span"]["start_line"],
        "end_line": normalized["span"]["end_line"],
    }


def _context_hit_for_node(
    node: dict[str, Any],
    score: float,
    content: dict[str, Any] | None,
    preview: str | None = None,
    span_node: dict[str, Any] | None = None,
    score_components: dict[str, float] | None = None,
    expanded_context: dict[str, Any] | None = None,
) -> ContextHit:
    normalized = _normalize_node(node)
    span = _normalize_node(span_node or node)
    text = str(content.get("text") or "") if content else ""
    return ContextHit(
        node_id=normalized["id"],
        stable_key=normalized["stable_key"],
        kind=normalized["kind"],
        file_path=span["span"]["file_path"],
        start_line=span["span"]["start_line"],
        end_line=span["span"]["end_line"],
        score=score,
        repository_id=normalized["repository_id"] or None,
        snapshot_id=normalized["snapshot_id"] or None,
        content_hash=str(content.get("hash") or normalized["content_hash"] or "")
        if content
        else normalized["content_hash"] or None,
        score_components=score_components or {},
        expanded_context=expanded_context,
        preview=preview or _preview(text),
    )


def _ranked_unique_hits(hits: list[ContextHit], limit: int) -> list[ContextHit]:
    if limit <= 0:
        return []

    best_by_node_id: dict[str, ContextHit] = {}
    for hit in hits:
        existing = best_by_node_id.get(hit.node_id)
        if existing is None:
            best_by_node_id[hit.node_id] = hit
        elif hit.score > existing.score:
            best_by_node_id[hit.node_id] = _merge_hit_score_components(hit, existing)
        else:
            best_by_node_id[hit.node_id] = _merge_hit_score_components(existing, hit)

    return sorted(
        best_by_node_id.values(),
        key=lambda hit: (hit.score, _kind_weight_from_name(hit.kind), -hit.start_line),
        reverse=True,
    )[:limit]


def _merge_hit_score_components(
    primary: ContextHit, secondary: ContextHit
) -> ContextHit:
    return primary.model_copy(
        update={
            "score_components": {
                **secondary.score_components,
                **primary.score_components,
            }
        }
    )


def _source_hit_count(hits: list[ContextHit], score_component: str) -> int:
    return sum(1 for hit in hits if score_component in hit.score_components)


def _search_mode(
    vector_hit_count: int, lexical_hit_count: int, summary_hit_count: int
) -> str:
    active = sum(
        1
        for count in [vector_hit_count, lexical_hit_count, summary_hit_count]
        if count > 0
    )
    if active > 1:
        return "hybrid"
    if vector_hit_count:
        return "vector"
    if lexical_hit_count:
        return "lexical"
    if summary_hit_count:
        return "summary"
    return "none"


def _candidate_limit(limit: int) -> int:
    if limit <= 0:
        return 0

    return min(max(limit * 8, 24), 120)


def _diversify_lexical_nodes(
    nodes: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    buckets: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        key = str(node.get("filePath") or node.get("id") or "")
        buckets.setdefault(key, []).append(node)

    selected: list[dict[str, Any]] = []
    while len(selected) < limit:
        added = False
        for bucket in buckets.values():
            if bucket:
                selected.append(bucket.pop(0))
                added = True
            if len(selected) >= limit:
                break
        if not added:
            break

    return selected


def _kind(node: dict[str, Any]) -> str:
    return str(node.get("kind") or "").casefold()


def _symbol_kind_filter(kinds: list[str]) -> list[str]:
    if not kinds:
        return sorted(_SYMBOL_KINDS)

    return sorted(
        {kind.casefold() for kind in kinds if kind and kind.casefold() in _SYMBOL_KINDS}
    )


def _kind_weight(node: dict[str, Any]) -> float:
    return _kind_weight_from_name(str(node.get("kind") or ""))


def _kind_weight_from_name(kind: str) -> float:
    return _KIND_WEIGHTS.get(kind.casefold(), 0.80)


def _needs_context_expansion(node: dict[str, Any]) -> bool:
    return _kind(node) in _LOW_SIGNAL_KINDS


def _choose_context_candidate(
    source: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    choices = list(candidates)
    if not _needs_context_expansion(source):
        choices.append({"node": source, "distance": 0, "reason": "self"})

    preferred = [
        choice
        for choice in choices
        if _kind(choice.get("node") or {}) in _PREFERRED_CONTEXT_KINDS
    ]
    pool = preferred or choices
    if not pool:
        return None

    return max(pool, key=_candidate_score)


def _candidate_score(candidate: dict[str, Any]) -> float:
    node = candidate.get("node") or {}
    distance = _int(candidate.get("distance"))
    kind = _kind(node)
    score = _kind_weight(node) - (distance * 0.08)
    if kind in {"method", "constructor"}:
        score += 0.22
    elif kind in {"class", "interface", "struct"}:
        score += 0.14
    elif kind == "file":
        score -= 0.04

    return score


def _expansion_bonus(
    source: dict[str, Any],
    selected: dict[str, Any],
    declaration: dict[str, Any] | None,
) -> float:
    bonus = 0.0
    if str(source.get("id") or "") != str(selected.get("id") or ""):
        bonus += 0.06
    if declaration is not None:
        bonus += 0.03

    return bonus


def _adjust_score(
    raw_score: float, kind_weight: float, expansion_bonus: float
) -> float:
    return max(0.0, min(1.0, (raw_score * kind_weight) + expansion_bonus))


def _summary_score(summary: dict[str, Any], search_text: str) -> float:
    if not search_text:
        return 0.5

    summary_text = str(summary.get("summary") or "").casefold()
    name = str(summary.get("name") or "").casefold()
    stable_key = str(summary.get("stable_key") or "").casefold()
    tags = [str(tag).casefold() for tag in summary.get("tags", []) if str(tag).strip()]

    if search_text == name or search_text in tags:
        return 0.92
    if search_text in name or search_text in stable_key:
        return 0.82
    if search_text in summary_text:
        return 0.72

    terms = [term for term in search_text.split() if term]
    if terms and all(term in summary_text for term in terms):
        return 0.68
    if terms and any(term in summary_text for term in terms):
        return 0.46

    return 0.25


def _node_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    metadata = (
        summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    )
    return {
        "id": str(summary.get("node_id") or ""),
        "stableKey": str(summary.get("stable_key") or summary.get("node_id") or ""),
        "kind": str(summary.get("kind") or "Unknown"),
        "name": str(summary.get("name") or summary.get("node_id") or ""),
        "language": str(metadata.get("language") or ""),
        "project": str(metadata.get("project") or ""),
        "repositoryId": str(summary.get("repository_id") or ""),
        "ingestionRunId": str(metadata.get("ingestionRunId") or ""),
        "filePath": str(metadata.get("filePath") or ""),
        "startLine": _int(metadata.get("startLine")),
        "startColumn": _int(metadata.get("startColumn")),
        "endLine": _int(metadata.get("endLine")),
        "endColumn": _int(metadata.get("endColumn")),
        "contentHash": str(summary.get("content_hash") or ""),
        "metadataJson": json.dumps(metadata),
    }


def _matches_filters(node: dict[str, Any], filters: dict[str, str]) -> bool:
    if not filters:
        return True

    metadata = _metadata(node.get("metadataJson"))
    for key, expected in filters.items():
        actual = node.get(key)
        if actual is None:
            actual = metadata.get(key)
        if str(actual or "") != expected:
            return False

    return True


def _matches_repository(node: dict[str, Any], repository_id: str | None) -> bool:
    if not repository_id:
        return True

    metadata = _metadata(node.get("metadataJson"))
    actual = node.get("repositoryId") or metadata.get("repositoryId")
    return str(actual or "") == repository_id


def _effective_filters(query: ContextQuery) -> dict[str, str]:
    filters = dict(query.filters)
    if query.repository_id:
        filters["repositoryId"] = query.repository_id
    return filters


def _lexical_score(node: dict[str, Any], search_text: str) -> float:
    if not search_text:
        return 0.5

    fields = [
        str(node.get("id") or "").casefold(),
        str(node.get("stableKey") or "").casefold(),
        str(node.get("name") or "").casefold(),
        str(node.get("filePath") or "").casefold(),
    ]

    if any(field == search_text for field in fields):
        return 1.0
    if any(field.startswith(search_text) for field in fields):
        return 0.85
    if any(search_text in field for field in fields):
        return 0.65

    terms = lexical_terms(search_text)
    if not terms:
        return 0.0

    matched_terms = sum(1 for term in terms if any(term in field for field in fields))
    coverage = matched_terms / len(terms)
    best_field_coverage = max(
        (sum(1 for term in terms if term in field) / len(terms) for field in fields),
        default=0.0,
    )
    file_name = fields[3].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    identifier_fields = [fields[2], file_name]
    identifier_coverage = sum(
        1 for term in terms if any(term in field for field in identifier_fields)
    ) / len(terms)
    return min(
        0.95,
        0.15
        + (coverage * 0.55)
        + (best_field_coverage * 0.10)
        + (identifier_coverage * 0.25),
    )


def _symbol_score(node: dict[str, Any], search_text: str) -> float:
    lexical_score = _symbol_lexical_score(node, search_text)
    return max(0.0, min(1.0, lexical_score * _kind_weight(node)))


def _symbol_score_components(
    node: dict[str, Any], search_text: str
) -> dict[str, float]:
    return {
        "lexical_score": _symbol_lexical_score(node, search_text),
        "kind_weight": _kind_weight(node),
    }


def _symbol_lexical_score(node: dict[str, Any], search_text: str) -> float:
    if not search_text:
        return 0.5

    metadata = _metadata(node.get("metadataJson"))
    exact_fields = [
        str(node.get("name") or "").casefold(),
        str(metadata.get("display") or "").casefold(),
    ]
    fields = [
        str(node.get("id") or "").casefold(),
        str(node.get("stableKey") or "").casefold(),
        str(node.get("name") or "").casefold(),
        str(node.get("filePath") or "").casefold(),
        str(metadata.get("display") or "").casefold(),
        str(metadata.get("namespace") or "").casefold(),
        str(metadata.get("containingType") or "").casefold(),
    ]

    if any(field == search_text for field in exact_fields):
        return 1.0
    if any(field == search_text for field in fields):
        return 0.95
    if any(field.endswith(f".{search_text}") for field in fields):
        return 0.90
    if any(field.startswith(search_text) for field in fields):
        return 0.82
    if any(search_text in field for field in fields):
        return 0.62

    return 0.20


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _preview(text: str, limit: int = 180) -> str | None:
    compact = " ".join(text.split())
    if not compact:
        return None
    return compact[:limit]


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
