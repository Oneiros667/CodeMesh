from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import Settings
from .models import ContextHit, ContextQuery, ContextResponse, HealthResponse, NeighborQuery, NodeLookup, NodeResponse

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

        return ContextResponse(query=query, hits=hits[: max(query.limit, 0)])

    async def get_node(self, lookup: NodeLookup) -> NodeResponse:
        node = await self._get_node_properties(lookup.node_id)
        if node is None:
            return NodeResponse()

        normalized_node = _normalize_node(node)
        content = None
        relationships: list[dict[str, Any]] = []

        if lookup.include_content:
            content_hash = str(node.get("contentHash") or "")
            content = await self._get_content(content_hash)

        if lookup.include_neighbors:
            relationships = await self._get_relationships(lookup.node_id, depth=1)

        return NodeResponse(node=normalized_node, content=content, relationships=relationships)

    async def get_neighbors(self, query: NeighborQuery) -> NodeResponse:
        relationships = await self._get_relationships(query.node_id, query.depth, query.relationship_kinds)
        return NodeResponse(relationships=relationships)

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

    async def _get_node_properties(self, node_id: str) -> dict[str, Any] | None:
        if AsyncGraphDatabase is None:
            return None

        try:
            driver = self._neo4j()
            async with driver.session(database=self._settings.neo4j_database) as session:
                result = await session.run(
                    "MATCH (n:CodeMeshNode {id: $node_id}) RETURN properties(n) AS node LIMIT 1",
                    node_id=node_id,
                )
                record = await result.single()

            return dict(record["node"]) if record else None
        except Exception:
            return None

    async def _get_relationships(
        self,
        node_id: str,
        depth: int = 1,
        relationship_kinds: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if AsyncGraphDatabase is None:
            return []

        clamped_depth = min(max(depth, 1), 4)
        query = f"""
        MATCH path = (:CodeMeshNode {{id: $node_id}})-[rels:CODEMESH_REL*1..{clamped_depth}]-()
        UNWIND rels AS relationship
        RETURN DISTINCT properties(relationship) AS relationship
        ORDER BY relationship.id
        """

        try:
            driver = self._neo4j()
            async with driver.session(database=self._settings.neo4j_database) as session:
                result = await session.run(query, node_id=node_id)
                records = await result.data()
        except Exception:
            return []

        kinds = {kind.casefold() for kind in relationship_kinds or []}
        relationships = [_normalize_relationship(dict(record["relationship"])) for record in records]
        if not kinds:
            return relationships

        return [item for item in relationships if str(item.get("kind", "")).casefold() in kinds]

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

    async def _search_lexical_context(self, query: ContextQuery) -> list[ContextHit]:
        if AsyncGraphDatabase is None:
            return []

        search_text = query.query.casefold()
        kinds = [kind.casefold() for kind in query.kinds]
        limit = min(max(query.limit * 4, 16), 200)

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
                    RETURN properties(n) AS node
                    LIMIT $limit
                    """,
                    search_text=search_text,
                    kinds=kinds,
                    limit=limit,
                )
                records = await result.data()
        except Exception:
            return []

        nodes = [dict(record["node"]) for record in records]
        nodes = [node for node in nodes if _matches_filters(node, query.filters)]
        nodes.sort(key=lambda node: _lexical_score(node, search_text), reverse=True)

        hits = []
        for node in nodes[: query.limit]:
            content = await self._get_content(str(node.get("contentHash") or ""))
            hits.append(_context_hit_for_node(node, _lexical_score(node, search_text), content))

        return hits

    async def _search_vector_context(self, query: ContextQuery, vector: list[float]) -> list[ContextHit]:
        qdrant_hits = await self._search_qdrant(vector, query.limit, query.filters)
        hits: list[ContextHit] = []

        for item in qdrant_hits:
            node_id = str(item.get("nodeId") or "")
            content_hash = str(item.get("contentHash") or "")
            node = await self._get_node_properties(node_id)
            content = await self._get_content(content_hash)

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
            hits.append(_context_hit_for_node(node, float(item.get("score") or 0), content, preview))

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


def _normalize_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(node.get("id") or ""),
        "stable_key": str(node.get("stableKey") or ""),
        "kind": str(node.get("kind") or ""),
        "name": str(node.get("name") or ""),
        "language": str(node.get("language") or ""),
        "project": str(node.get("project") or ""),
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
        "id": str(relationship.get("id") or ""),
        "source_node_id": str(relationship.get("sourceNodeId") or ""),
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


def _context_hit_for_node(
    node: dict[str, Any],
    score: float,
    content: dict[str, Any] | None,
    preview: str | None = None,
) -> ContextHit:
    normalized = _normalize_node(node)
    text = str(content.get("text") or "") if content else ""
    return ContextHit(
        node_id=normalized["id"],
        stable_key=normalized["stable_key"],
        kind=normalized["kind"],
        file_path=normalized["span"]["file_path"],
        start_line=normalized["span"]["start_line"],
        end_line=normalized["span"]["end_line"],
        score=score,
        preview=preview or _preview(text),
    )


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


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
