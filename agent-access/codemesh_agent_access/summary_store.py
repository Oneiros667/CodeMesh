from __future__ import annotations

import asyncio
import re
from typing import Any

from .config import Settings
from .content_store import MongoClient, PyMongoError, datetime_value, string_dict


class MongoNodeSummaryStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._mongo_client: Any | None = None

    async def close(self) -> None:
        client = self._mongo_client
        self._mongo_client = None
        if client is not None:
            await asyncio.to_thread(client.close)

    async def health(self) -> dict[str, Any]:
        if MongoClient is None:
            return {
                "uri": self._settings.mongo_uri,
                "database": self._settings.mongo_database,
                "collection": self._settings.mongo_node_summaries_collection,
                "status": "degraded",
                "detail": "The pymongo package is not installed.",
            }

        try:
            await asyncio.to_thread(self._mongo().admin.command, "ping")
            return {
                "uri": self._settings.mongo_uri,
                "database": self._settings.mongo_database,
                "collection": self._settings.mongo_node_summaries_collection,
                "status": "healthy",
            }
        except PyMongoError as exc:  # pragma: no cover - depends on local store state
            return {
                "uri": self._settings.mongo_uri,
                "database": self._settings.mongo_database,
                "collection": self._settings.mongo_node_summaries_collection,
                "status": "degraded",
                "detail": str(exc),
            }

    async def get_node_summary(
        self,
        repository_id: str | None,
        node_id: str,
        content_hash: str | None,
    ) -> dict[str, Any] | None:
        if not repository_id or not node_id or MongoClient is None:
            return None

        query: dict[str, Any] = {
            "repositoryId": repository_id,
            "nodeId": node_id,
            "status": "completed",
        }
        if content_hash:
            query["contentHash"] = content_hash

        def find_one() -> dict[str, Any] | None:
            collection = self._mongo()[self._settings.mongo_database][
                self._settings.mongo_node_summaries_collection
            ]
            document = collection.find_one(query, sort=[("generatedAtUtc", -1)])
            if document is None and content_hash:
                fallback_query = dict(query)
                fallback_query.pop("contentHash", None)
                document = collection.find_one(
                    fallback_query, sort=[("generatedAtUtc", -1)]
                )
            return dict(document) if document else None

        try:
            document = await asyncio.to_thread(find_one)
        except PyMongoError:
            return None

        return normalize_node_summary(document) if document else None

    async def search_summaries(
        self,
        query: str,
        repository_id: str | None,
        kinds: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        if not query.strip() or limit <= 0 or MongoClient is None:
            return []

        filter_query: dict[str, Any] = {"status": "completed"}
        if repository_id:
            filter_query["repositoryId"] = repository_id
        if kinds:
            filter_query["kind"] = {"$in": _kind_variants(kinds)}

        patterns = [
            re.compile(re.escape(term), re.IGNORECASE)
            for term in query.strip().split()
            if term.strip()
        ]
        if not patterns:
            return []

        filter_query["$or"] = [
            {field: pattern}
            for pattern in patterns
            for field in ["summary", "name", "stableKey", "tags"]
        ]

        def find() -> list[dict[str, Any]]:
            collection = self._mongo()[self._settings.mongo_database][
                self._settings.mongo_node_summaries_collection
            ]
            return [
                dict(document)
                for document in collection.find(filter_query)
                .sort("generatedAtUtc", -1)
                .limit(max(1, min(limit, 200)))
            ]

        try:
            documents = await asyncio.to_thread(find)
        except PyMongoError:
            return []

        return [normalize_node_summary(document) for document in documents]

    async def summary_coverage(self, repository_id: str) -> dict[str, Any]:
        if not repository_id or MongoClient is None:
            return _empty_summary_coverage(repository_id)

        def aggregate() -> dict[str, Any]:
            collection = self._mongo()[self._settings.mongo_database][
                self._settings.mongo_node_summaries_collection
            ]
            base_filter = {"repositoryId": repository_id}

            total_count = collection.count_documents(base_filter)
            status_counts = _count_by(collection, base_filter, "status")
            kind_counts = _count_by(collection, base_filter, "kind")
            provider_model_counts = _count_by_provider_model(collection, base_filter)
            provider_model_count_details = _count_by_provider_model_details(
                collection, base_filter
            )
            recent_failures = [
                normalize_node_summary(document)
                | {"error": str(document.get("error") or "")}
                for document in collection.find({**base_filter, "status": "failed"})
                .sort("generatedAtUtc", -1)
                .limit(10)
            ]

            return {
                "repository_id": repository_id,
                "total_count": total_count,
                "completed_count": status_counts.get("completed", 0),
                "failed_count": status_counts.get("failed", 0),
                "status_counts": status_counts,
                "kind_counts": kind_counts,
                "provider_model_counts": provider_model_counts,
                "provider_model_count_details": provider_model_count_details,
                "recent_failures": recent_failures,
            }

        try:
            return await asyncio.to_thread(aggregate)
        except PyMongoError:
            return _empty_summary_coverage(repository_id)

    async def delete_repository(self, repository_id: str) -> None:
        if not repository_id or MongoClient is None:
            return

        def delete() -> None:
            collection = self._mongo()[self._settings.mongo_database][
                self._settings.mongo_node_summaries_collection
            ]
            collection.delete_many({"repositoryId": repository_id})

        await asyncio.to_thread(delete)

    def _mongo(self) -> Any:
        if MongoClient is None:
            raise RuntimeError("The pymongo package is not installed.")

        if self._mongo_client is None:
            self._mongo_client = MongoClient(
                self._settings.mongo_uri, serverSelectionTimeoutMS=2000
            )

        return self._mongo_client


def normalize_node_summary(document: dict[str, Any]) -> dict[str, Any]:
    tags = document.get("tags")
    return {
        "id": str(document.get("_id") or document.get("id") or ""),
        "repository_id": str(document.get("repositoryId") or ""),
        "node_id": str(document.get("nodeId") or ""),
        "stable_key": str(document.get("stableKey") or ""),
        "kind": str(document.get("kind") or ""),
        "name": str(document.get("name") or ""),
        "content_hash": str(document.get("contentHash") or ""),
        "summary_kind": str(document.get("summaryKind") or ""),
        "summary": str(document.get("summary") or ""),
        "tags": [str(tag) for tag in tags] if isinstance(tags, list) else [],
        "confidence": str(document.get("confidence") or ""),
        "provider": str(document.get("provider") or ""),
        "model": str(document.get("model") or ""),
        "prompt_version": str(document.get("promptVersion") or ""),
        "generated_at": datetime_value(document.get("generatedAtUtc")),
        "metadata": string_dict(document.get("metadata")),
    }


def _kind_variants(kinds: list[str]) -> list[str]:
    values: set[str] = set()
    for kind in kinds:
        text = str(kind or "").strip()
        if not text:
            continue

        values.add(text)
        values.add(text.casefold())
        values.add(text[:1].upper() + text[1:].lower())

    return sorted(values)


def _empty_summary_coverage(repository_id: str) -> dict[str, Any]:
    return {
        "repository_id": repository_id,
        "total_count": 0,
        "completed_count": 0,
        "failed_count": 0,
        "status_counts": {},
        "kind_counts": {},
        "provider_model_counts": {},
        "provider_model_count_details": [],
        "recent_failures": [],
    }


def _count_by(
    collection: Any, base_filter: dict[str, Any], field: str
) -> dict[str, int]:
    return {
        str(item.get("_id") or "unknown"): int(item.get("count") or 0)
        for item in collection.aggregate(
            [
                {"$match": base_filter},
                {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
                {"$sort": {"count": -1, "_id": 1}},
            ]
        )
    }


def _count_by_provider_model(
    collection: Any, base_filter: dict[str, Any]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in collection.aggregate(
        [
            {"$match": base_filter},
            {
                "$group": {
                    "_id": {
                        "provider": "$provider",
                        "model": "$model",
                        "promptVersion": "$promptVersion",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
        ]
    ):
        key = item.get("_id") if isinstance(item.get("_id"), dict) else {}
        provider = str(key.get("provider") or "unknown")
        model = str(key.get("model") or "unknown")
        prompt_version = str(key.get("promptVersion") or "unknown")
        counts[f"{provider}/{model}/{prompt_version}"] = int(item.get("count") or 0)

    return counts


def _count_by_provider_model_details(
    collection: Any, base_filter: dict[str, Any]
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for item in collection.aggregate(
        [
            {"$match": base_filter},
            {
                "$group": {
                    "_id": {
                        "provider": "$provider",
                        "model": "$model",
                        "promptVersion": "$promptVersion",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
        ]
    ):
        key = item.get("_id") if isinstance(item.get("_id"), dict) else {}
        details.append(
            {
                "provider": str(key.get("provider") or "unknown"),
                "model": str(key.get("model") or "unknown"),
                "prompt_version": str(key.get("promptVersion") or "unknown"),
                "count": int(item.get("count") or 0),
            }
        )

    return details
