from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import Settings
from .models import (
    ContextHit,
    ContextQuery,
    ContextResponse,
    HealthResponse,
    IngestionRunListResponse,
    IngestionRunSummary,
    NeighborQuery,
    NodeLookup,
    NodeResponse,
    RepositoryListResponse,
    RepositorySummary,
)

try:
    from neo4j import AsyncGraphDatabase
except ImportError:  # pragma: no cover - exercised only when dependencies are missing
    AsyncGraphDatabase = None  # type: ignore[assignment]

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError:  # pragma: no cover - exercised only when dependencies are missing
    MongoClient = None  # type: ignore[assignment]
    PyMongoError = Exception  # type: ignore[assignment]


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
}

_DECLARABLE_SYMBOL_KINDS = {
    "class",
    "interface",
    "struct",
    "enum",
    "delegate",
    "method",
    "constructor",
    "property",
    "field",
    "event",
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
        self._neo4j_driver: Any | None = None
        self._mongo_client: Any | None = None

    async def health(self) -> HealthResponse:
        components = {
            "neo4j": await self._neo4j_health(),
            "mongodb": await self._mongo_health(),
            "qdrant": await self._qdrant_health(),
            "model_provider": await self._model_provider_health(),
        }
        status = "healthy" if all(_component_ok(value) for value in components.values()) else "degraded"
        return HealthResponse(status=status, components=components)

    async def search_context(self, query: ContextQuery) -> ContextResponse:
        vector = query.vector
        if not vector and self._settings.model_provider.casefold() == "ollama" and query.query.strip():
            vector = await self._embed_query(query.query)

        hits = await self._search_vector_context(query, vector) if vector else []
        if not hits:
            hits = await self._search_lexical_context(query)

        return ContextResponse(query=query, hits=_ranked_unique_hits(hits, query.limit))

    async def get_node(self, lookup: NodeLookup) -> NodeResponse:
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
            relationships = await self._get_relationships(lookup.node_id, lookup.repository_id, depth=1)

        return NodeResponse(node=normalized_node, content=content, relationships=relationships)

    async def get_neighbors(self, query: NeighborQuery) -> NodeResponse:
        relationships = await self._get_relationships(
            query.node_id,
            query.repository_id,
            query.depth,
            query.relationship_kinds)
        return NodeResponse(relationships=relationships)

    async def list_repositories(self, limit: int = 50) -> RepositoryListResponse:
        if MongoClient is None:
            return RepositoryListResponse()

        collection = self._mongo()[self._settings.mongo_database][self._settings.mongo_repositories_collection]
        documents = await asyncio.to_thread(
            lambda: list(
                collection.find({})
                .sort("lastSeenAtUtc", -1)
                .limit(max(1, min(limit, 500)))
            )
        )

        return RepositoryListResponse(
            repositories=[_normalize_repository(document) for document in documents]
        )

    async def get_repository(self, repository_id: str) -> RepositorySummary | None:
        if MongoClient is None:
            return None

        collection = self._mongo()[self._settings.mongo_database][self._settings.mongo_repositories_collection]
        document = await asyncio.to_thread(collection.find_one, {"_id": repository_id})
        return _normalize_repository(document) if document else None

    async def list_ingestion_runs(
        self,
        repository_id: str | None = None,
        limit: int = 50,
    ) -> IngestionRunListResponse:
        if MongoClient is None:
            return IngestionRunListResponse()

        filter_query = {"repositoryId": repository_id} if repository_id else {}
        collection = self._mongo()[self._settings.mongo_database][self._settings.mongo_ingestion_runs_collection]
        documents = await asyncio.to_thread(
            lambda: list(
                collection.find(filter_query)
                .sort("startedAtUtc", -1)
                .limit(max(1, min(limit, 500)))
            )
        )

        return IngestionRunListResponse(
            runs=[_normalize_ingestion_run(document) for document in documents]
        )

    async def _neo4j_health(self) -> dict[str, Any]:
        if AsyncGraphDatabase is None:
            return {
                "uri": self._settings.neo4j_uri,
                "database": self._settings.neo4j_database,
                "status": "degraded",
                "detail": "The neo4j Python package is not installed.",
            }

        try:
            driver = self._neo4j()
            async with driver.session(database=self._settings.neo4j_database) as session:
                result = await session.run("RETURN 1 AS ok")
                await result.consume()

            return {
                "uri": self._settings.neo4j_uri,
                "database": self._settings.neo4j_database,
                "status": "healthy",
            }
        except Exception as exc:  # pragma: no cover - depends on local store state
            return {
                "uri": self._settings.neo4j_uri,
                "database": self._settings.neo4j_database,
                "status": "degraded",
                "detail": str(exc),
            }

    async def _mongo_health(self) -> dict[str, Any]:
        if MongoClient is None:
            return {
                "uri": self._settings.mongo_uri,
                "database": self._settings.mongo_database,
                "collection": self._settings.mongo_content_collection,
                "status": "degraded",
                "detail": "The pymongo package is not installed.",
            }

        try:
            await asyncio.to_thread(self._mongo().admin.command, "ping")
            return {
                "uri": self._settings.mongo_uri,
                "database": self._settings.mongo_database,
                "collection": self._settings.mongo_content_collection,
                "status": "healthy",
            }
        except PyMongoError as exc:  # pragma: no cover - depends on local store state
            return {
                "uri": self._settings.mongo_uri,
                "database": self._settings.mongo_database,
                "collection": self._settings.mongo_content_collection,
                "status": "degraded",
                "detail": str(exc),
            }

    async def _qdrant_health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self._qdrant_url()}/collections")
                response.raise_for_status()

            return {
                "url": self._settings.qdrant_url,
                "collection": self._settings.qdrant_collection,
                "status": "healthy",
            }
        except httpx.HTTPError as exc:  # pragma: no cover - depends on local store state
            return {
                "url": self._settings.qdrant_url,
                "collection": self._settings.qdrant_collection,
                "status": "degraded",
                "detail": str(exc),
            }

    async def _model_provider_health(self) -> dict[str, Any]:
        provider = self._settings.model_provider.casefold()
        if provider == "none":
            return {"provider": "none", "status": "configured"}

        if provider != "ollama":
            return {
                "provider": self._settings.model_provider,
                "status": "degraded",
                "detail": "Unsupported model provider for Agent Access embeddings.",
            }

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self._ollama_url()}/api/tags")
                response.raise_for_status()

            return {
                "provider": "ollama",
                "url": self._settings.ollama_url,
                "embedding_model": self._settings.embedding_model,
                "status": "healthy",
            }
        except httpx.HTTPError as exc:  # pragma: no cover - depends on local model service state
            return {
                "provider": "ollama",
                "url": self._settings.ollama_url,
                "embedding_model": self._settings.embedding_model,
                "status": "degraded",
                "detail": str(exc),
            }

    async def _get_node_properties(self, node_id: str, repository_id: str | None = None) -> dict[str, Any] | None:
        if AsyncGraphDatabase is None:
            return None

        try:
            driver = self._neo4j()
            async with driver.session(database=self._settings.neo4j_database) as session:
                if repository_id:
                    result = await session.run(
                        "MATCH (n:CodeMeshNode {storageKey: $storage_key}) RETURN properties(n) AS node LIMIT 1",
                        storage_key=_storage_key(repository_id, node_id),
                    )
                else:
                    result = await session.run(
                        """
                        MATCH (n:CodeMeshNode {id: $node_id})
                        RETURN properties(n) AS node
                        ORDER BY n.lastSeenAt DESC
                        LIMIT 1
                        """,
                        node_id=node_id,
                    )
                record = await result.single()

            return dict(record["node"]) if record else None
        except Exception:
            return None

    async def _get_relationships(
        self,
        node_id: str,
        repository_id: str | None = None,
        depth: int = 1,
        relationship_kinds: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if AsyncGraphDatabase is None:
            return []

        clamped_depth = min(max(depth, 1), 4)
        if repository_id:
            query = f"""
            MATCH path = (:CodeMeshNode {{storageKey: $storage_key}})-[rels:CODEMESH_REL*1..{clamped_depth}]-()
            UNWIND rels AS relationship
            RETURN DISTINCT properties(relationship) AS relationship
            ORDER BY relationship.id
            """
            parameters = {"storage_key": _storage_key(repository_id, node_id)}
        else:
            query = f"""
            MATCH path = (:CodeMeshNode {{id: $node_id}})-[rels:CODEMESH_REL*1..{clamped_depth}]-()
            UNWIND rels AS relationship
            RETURN DISTINCT properties(relationship) AS relationship
            ORDER BY relationship.id
            """
            parameters = {"node_id": node_id}

        try:
            driver = self._neo4j()
            async with driver.session(database=self._settings.neo4j_database) as session:
                result = await session.run(query, **parameters)
                records = await result.data()
        except Exception:
            return []

        kinds = {kind.casefold() for kind in relationship_kinds or []}
        relationships = [_normalize_relationship(dict(record["relationship"])) for record in records]
        if not kinds:
            return relationships

        return [item for item in relationships if str(item.get("kind", "")).casefold() in kinds]

    async def _get_context_candidates(
        self,
        node_id: str,
        repository_id: str | None = None,
        depth: int = 4,
    ) -> list[dict[str, Any]]:
        if AsyncGraphDatabase is None:
            return []

        clamped_depth = min(max(depth, 1), 6)
        if repository_id:
            start_match = "MATCH (start:CodeMeshNode {storageKey: $storage_key})"
            parameters = {"storage_key": _storage_key(repository_id, node_id)}
        else:
            start_match = "MATCH (start:CodeMeshNode {id: $node_id})"
            parameters = {"node_id": node_id}

        query = f"""
        {start_match}
        CALL (start) {{
          MATCH (start)-[relationship:CODEMESH_REL]->(defined:CodeMeshNode)
          WHERE relationship.kind = 'Defines'
          RETURN properties(defined) AS node, 0 AS distance, 'defines' AS reason
          UNION
          MATCH path = (ancestor:CodeMeshNode)-[relationships:CODEMESH_REL*1..{clamped_depth}]->(start)
          WHERE all(relationship IN relationships WHERE relationship.kind = 'Contains')
          RETURN properties(ancestor) AS node, length(path) AS distance, 'ancestor' AS reason
          UNION
          MATCH (start)-[defines:CODEMESH_REL]->(defined:CodeMeshNode)
          WHERE defines.kind = 'Defines'
          MATCH path = (ancestor:CodeMeshNode)-[relationships:CODEMESH_REL*1..{clamped_depth}]->(defined)
          WHERE all(relationship IN relationships WHERE relationship.kind = 'Contains')
          RETURN properties(ancestor) AS node, length(path) AS distance, 'defined_ancestor' AS reason
        }}
        RETURN node, distance, reason
        """

        try:
            driver = self._neo4j()
            async with driver.session(database=self._settings.neo4j_database) as session:
                result = await session.run(query, **parameters)
                records = await result.data()
        except Exception:
            return []

        return [
            {
                "node": dict(record["node"]),
                "distance": _int(record.get("distance")),
                "reason": str(record.get("reason") or "context"),
            }
            for record in records
            if record.get("node")
        ]

    async def _get_primary_declaration_node(
        self,
        node: dict[str, Any],
        repository_id: str | None = None,
    ) -> dict[str, Any] | None:
        if AsyncGraphDatabase is None or _kind(node) not in _DECLARABLE_SYMBOL_KINDS:
            return None

        node_id = str(node.get("id") or "")
        if not node_id:
            return None

        if repository_id:
            symbol_match = "MATCH (symbol:CodeMeshNode {storageKey: $storage_key})"
            parameters = {"storage_key": _storage_key(repository_id, node_id)}
        else:
            symbol_match = "MATCH (symbol:CodeMeshNode {id: $node_id})"
            parameters = {"node_id": node_id}

        query = f"""
        {symbol_match}
        MATCH (declaration:CodeMeshNode)-[relationship:CODEMESH_REL]->(symbol)
        WHERE relationship.kind = 'Defines' AND declaration.kind = 'Declaration'
        RETURN properties(declaration) AS node
        ORDER BY declaration.startLine
        LIMIT 1
        """

        try:
            driver = self._neo4j()
            async with driver.session(database=self._settings.neo4j_database) as session:
                result = await session.run(query, **parameters)
                record = await result.single()
        except Exception:
            return None

        return dict(record["node"]) if record else None

    async def _get_context_relationship_summaries(
        self,
        node_id: str,
        repository_id: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        if AsyncGraphDatabase is None or limit <= 0:
            return []

        clamped_limit = min(max(limit, 1), 50)
        if repository_id:
            node_match = "MATCH (node:CodeMeshNode {storageKey: $storage_key})"
            parameters = {"storage_key": _storage_key(repository_id, node_id), "limit": clamped_limit}
        else:
            node_match = "MATCH (node:CodeMeshNode {id: $node_id})"
            parameters = {"node_id": node_id, "limit": clamped_limit}

        query = f"""
        {node_match}
        MATCH (node)-[relationship:CODEMESH_REL]-(other:CodeMeshNode)
        RETURN properties(relationship) AS relationship, properties(other) AS other
        ORDER BY
          CASE relationship.kind
            WHEN 'Defines' THEN 0
            WHEN 'Contains' THEN 1
            WHEN 'Invokes' THEN 2
            WHEN 'UsesType' THEN 3
            WHEN 'Returns' THEN 4
            ELSE 9
          END,
          coalesce(other.name, other.id, '')
        LIMIT $limit
        """

        try:
            driver = self._neo4j()
            async with driver.session(database=self._settings.neo4j_database) as session:
                result = await session.run(query, **parameters)
                records = await result.data()
        except Exception:
            return []

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

        return summaries

    async def _get_content(self, content_hash: str) -> dict[str, Any] | None:
        if not content_hash or MongoClient is None:
            return None

        def find_one() -> dict[str, Any] | None:
            collection = self._mongo()[self._settings.mongo_database][self._settings.mongo_content_collection]
            document = collection.find_one({"_id": content_hash})
            return dict(document) if document else None

        try:
            document = await asyncio.to_thread(find_one)
        except PyMongoError:
            return None

        return _normalize_content(document) if document else None

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

        candidates = await self._get_context_candidates(node_id, repository_id, context_depth)
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
        content_hash = str(content_node.get("contentHash") or selected.get("contentHash") or source.get("contentHash") or "")
        content = await self._get_content(content_hash)
        selected_id = str(selected.get("id") or "")
        source_id = str(source.get("id") or "")
        declaration_id = str(declaration.get("id") or "") if declaration else ""
        selected_own_preview = preview if selected_id == source_id and not declaration else None
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
        if AsyncGraphDatabase is None:
            return []

        search_text = query.query.casefold()
        kinds = [kind.casefold() for kind in query.kinds]
        limit = min(max(query.limit * 4, 16), 200)
        repository_id = query.repository_id

        try:
            driver = self._neo4j()
            async with driver.session(database=self._settings.neo4j_database) as session:
                result = await session.run(
                    """
                    MATCH (n:CodeMeshNode)
                    WHERE
                        ($search_text = "" OR
                         toLower(coalesce(n.id, "")) CONTAINS $search_text OR
                         toLower(coalesce(n.stableKey, "")) CONTAINS $search_text OR
                         toLower(coalesce(n.name, "")) CONTAINS $search_text OR
                         toLower(coalesce(n.filePath, "")) CONTAINS $search_text)
                        AND (size($kinds) = 0 OR toLower(coalesce(n.kind, "")) IN $kinds)
                        AND ($repository_id IS NULL OR n.repositoryId = $repository_id)
                    RETURN properties(n) AS node
                    LIMIT $limit
                    """,
                    search_text=search_text,
                    kinds=kinds,
                    repository_id=repository_id,
                    limit=limit,
                )
                records = await result.data()
        except Exception:
            return []

        nodes = [dict(record["node"]) for record in records]
        nodes = [
            node for node in nodes
            if _matches_filters(node, query.filters) and _matches_repository(node, query.repository_id)
        ]
        nodes.sort(key=lambda node: _lexical_score(node, search_text), reverse=True)

        hits = []
        for node in nodes[: _candidate_limit(query.limit)]:
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

    async def _search_vector_context(self, query: ContextQuery, vector: list[float]) -> list[ContextHit]:
        qdrant_hits = await self._search_qdrant(vector, _candidate_limit(query.limit), _effective_filters(query))
        hits: list[ContextHit] = []

        for item in qdrant_hits:
            node_id = str(item.get("nodeId") or "")
            content_hash = str(item.get("contentHash") or "")
            repository_id = query.repository_id or str(item.get("repositoryId") or "") or None
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

    async def _search_qdrant(
        self,
        vector: list[float],
        limit: int,
        filters: dict[str, str],
    ) -> list[dict[str, Any]]:
        if not vector or limit <= 0:
            return []

        body: dict[str, Any] = {
            "vector": vector,
            "limit": limit,
            "with_payload": True,
        }
        qdrant_filter = _qdrant_filter(filters)
        if qdrant_filter:
            body["filter"] = qdrant_filter

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self._qdrant_url()}/collections/{self._settings.qdrant_collection}/points/search",
                    json=body,
                )
                if response.status_code == 404:
                    return []
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError:
            return []

        return [
            {
                "nodeId": hit.get("payload", {}).get("nodeId", ""),
                "contentHash": hit.get("payload", {}).get("contentHash", ""),
                "repositoryId": hit.get("payload", {}).get("repositoryId", ""),
                "storageKey": hit.get("payload", {}).get("storageKey", ""),
                "preview": hit.get("payload", {}).get("preview"),
                "score": hit.get("score", 0),
            }
            for hit in payload.get("result", [])
        ]

    async def _embed_query(self, query: str) -> list[float]:
        body = {
            "model": self._settings.embedding_model,
            "input": [query],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self._ollama_url()}/api/embed", json=body)
                if response.status_code in {404, 405}:
                    return await self._embed_query_legacy(query, client)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError:
            return []

        embeddings = payload.get("embeddings") or []
        if not embeddings:
            return []

        return [float(value) for value in embeddings[0]]

    async def _embed_query_legacy(self, query: str, client: httpx.AsyncClient) -> list[float]:
        try:
            response = await client.post(
                f"{self._ollama_url()}/api/embeddings",
                json={"model": self._settings.embedding_model, "prompt": query},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError:
            return []

        return [float(value) for value in payload.get("embedding") or []]

    def _neo4j(self) -> Any:
        if AsyncGraphDatabase is None:
            raise RuntimeError("The neo4j Python package is not installed.")

        if self._neo4j_driver is None:
            self._neo4j_driver = AsyncGraphDatabase.driver(
                self._settings.neo4j_uri,
                auth=(self._settings.neo4j_user, self._settings.neo4j_password),
            )

        return self._neo4j_driver

    def _mongo(self) -> Any:
        if MongoClient is None:
            raise RuntimeError("The pymongo package is not installed.")

        if self._mongo_client is None:
            self._mongo_client = MongoClient(self._settings.mongo_uri, serverSelectionTimeoutMS=2000)

        return self._mongo_client

    def _qdrant_url(self) -> str:
        return self._settings.qdrant_url.rstrip("/")

    def _ollama_url(self) -> str:
        return self._settings.ollama_url.rstrip("/")


def _component_ok(component: Any) -> bool:
    return isinstance(component, dict) and component.get("status") in {"healthy", "configured"}


def _storage_key(repository_id: str, node_id: str) -> str:
    return f"{repository_id}:{node_id}"


def _normalize_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "storage_key": str(node.get("storageKey") or ""),
        "id": str(node.get("id") or ""),
        "stable_key": str(node.get("stableKey") or ""),
        "kind": str(node.get("kind") or ""),
        "name": str(node.get("name") or ""),
        "language": str(node.get("language") or ""),
        "project": str(node.get("project") or ""),
        "repository_id": str(node.get("repositoryId") or ""),
        "ingestion_run_id": str(node.get("ingestionRunId") or ""),
        "span": {
            "file_path": str(node.get("filePath") or ""),
            "start_line": _int(node.get("startLine")),
            "start_column": _int(node.get("startColumn")),
            "end_line": _int(node.get("endLine")),
            "end_column": _int(node.get("endColumn")),
        },
        "content_hash": str(node.get("contentHash") or ""),
        "metadata": _metadata(node.get("metadataJson")),
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


def _normalize_content(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "hash": str(document.get("_id") or document.get("hash") or ""),
        "text": str(document.get("text") or ""),
        "media_type": str(document.get("mediaType") or ""),
        "created_at": _datetime_value(document.get("createdAtUtc")),
        "updated_at": _datetime_value(document.get("updatedAtUtc")),
    }


def _normalize_repository(document: dict[str, Any]) -> RepositorySummary:
    return RepositorySummary(
        repository_id=str(document.get("_id") or document.get("repositoryId") or ""),
        root_path=str(document.get("rootPath") or ""),
        remote_url=_optional_str(document.get("remoteUrl")),
        branch=_optional_str(document.get("branch")),
        commit=_optional_str(document.get("commit")),
        first_seen_at=_datetime_value(document.get("firstSeenAtUtc")),
        last_seen_at=_datetime_value(document.get("lastSeenAtUtc")),
        last_run_id=_optional_str(document.get("lastRunId")),
        last_stage=_optional_str(document.get("lastStage")),
        last_message=_optional_str(document.get("lastMessage")),
        node_count=_int(document.get("nodeCount")),
        relationship_count=_int(document.get("relationshipCount")),
        content_count=_int(document.get("contentCount")),
        embedding_count=_optional_int(document.get("embeddingCount")),
        metadata=_string_dict(document.get("metadata")),
    )


def _normalize_ingestion_run(document: dict[str, Any]) -> IngestionRunSummary:
    return IngestionRunSummary(
        run_id=str(document.get("_id") or document.get("runId") or ""),
        repository_id=str(document.get("repositoryId") or ""),
        repository_root=str(document.get("repositoryRoot") or ""),
        stage=str(document.get("stage") or ""),
        started_at=_datetime_value(document.get("startedAtUtc")),
        finished_at=_datetime_value(document.get("finishedAtUtc")),
        message=_optional_str(document.get("message")),
        language=str(document.get("language") or ""),
        parser_name=str(document.get("parserName") or ""),
        solution_path=_optional_str(document.get("solutionPath")),
        project_path=_optional_str(document.get("projectPath")),
        dry_run=bool(document.get("dryRun") or False),
        skip_embeddings=bool(document.get("skipEmbeddings") if document.get("skipEmbeddings") is not None else True),
        embedding_provider=str(document.get("embeddingProvider") or ""),
        embedding_model=str(document.get("embeddingModel") or ""),
        node_count=_int(document.get("nodeCount")),
        relationship_count=_int(document.get("relationshipCount")),
        content_count=_int(document.get("contentCount")),
        embedding_count=_int(document.get("embeddingCount")),
        stats=_normalize_stats(document.get("stats")),
        diagnostic_count=_int(document.get("diagnosticCount")),
        error_diagnostic_count=_int(document.get("errorDiagnosticCount")),
        warning_diagnostic_count=_int(document.get("warningDiagnosticCount")),
        metadata=_string_dict(document.get("metadata")),
    )


def _normalize_stats(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    return {
        "parsed_node_count": _int(value.get("ParsedNodeCount") or value.get("parsedNodeCount")),
        "written_node_count": _int(value.get("WrittenNodeCount") or value.get("writtenNodeCount")),
        "skipped_node_count": _int(value.get("SkippedNodeCount") or value.get("skippedNodeCount")),
        "parsed_relationship_count": _int(value.get("ParsedRelationshipCount") or value.get("parsedRelationshipCount")),
        "written_relationship_count": _int(value.get("WrittenRelationshipCount") or value.get("writtenRelationshipCount")),
        "skipped_relationship_count": _int(value.get("SkippedRelationshipCount") or value.get("skippedRelationshipCount")),
        "parsed_content_count": _int(value.get("ParsedContentCount") or value.get("parsedContentCount")),
        "written_content_count": _int(value.get("WrittenContentCount") or value.get("writtenContentCount")),
        "skipped_content_count": _int(value.get("SkippedContentCount") or value.get("skippedContentCount")),
        "written_embedding_count": _int(value.get("WrittenEmbeddingCount") or value.get("writtenEmbeddingCount")),
        "skipped_embedding_count": _int(value.get("SkippedEmbeddingCount") or value.get("skippedEmbeddingCount")),
    }


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
        content_hash=str(content.get("hash") or normalized["content_hash"] or "") if content else normalized["content_hash"] or None,
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
        if existing is None or hit.score > existing.score:
            best_by_node_id[hit.node_id] = hit

    return sorted(
        best_by_node_id.values(),
        key=lambda hit: (hit.score, _kind_weight_from_name(hit.kind), -hit.start_line),
        reverse=True,
    )[:limit]


def _candidate_limit(limit: int) -> int:
    if limit <= 0:
        return 0

    return min(max(limit * 8, 24), 120)


def _kind(node: dict[str, Any]) -> str:
    return str(node.get("kind") or "").casefold()


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

    preferred = [choice for choice in choices if _kind(choice.get("node") or {}) in _PREFERRED_CONTEXT_KINDS]
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


def _adjust_score(raw_score: float, kind_weight: float, expansion_bonus: float) -> float:
    return max(0.0, min(1.0, (raw_score * kind_weight) + expansion_bonus))


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


def _qdrant_filter(filters: dict[str, str]) -> dict[str, Any] | None:
    if not filters:
        return None

    return {
        "must": [
            {
                "key": key,
                "match": {"value": value},
            }
            for key, value in filters.items()
        ]
    }


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

    return 0.25


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


def _datetime_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None

    return _int(value)


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    return {str(key): str(item) for key, item in value.items()}


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
