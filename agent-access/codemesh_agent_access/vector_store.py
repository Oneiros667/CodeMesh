from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class QdrantSearchClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def health(self) -> dict[str, Any]:
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

    async def search(
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
        qdrant_filter = qdrant_filter_for(filters)
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

    def _qdrant_url(self) -> str:
        return self._settings.qdrant_url.rstrip("/")


def qdrant_filter_for(filters: dict[str, str]) -> dict[str, Any] | None:
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
