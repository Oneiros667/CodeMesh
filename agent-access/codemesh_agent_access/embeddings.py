from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class QueryEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider(self) -> str:
        return model_provider(self._settings.model_provider)

    @property
    def is_enabled(self) -> bool:
        return self.provider in {"ollama", "lmstudio"}

    async def health(self) -> dict[str, Any]:
        provider = self.provider
        if provider == "none":
            return {"provider": "none", "status": "configured"}

        if provider not in {"ollama", "lmstudio"}:
            return {
                "provider": self._settings.model_provider,
                "status": "degraded",
                "detail": "Unsupported model provider for Agent Access embeddings.",
            }

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(self._health_url(provider))
                response.raise_for_status()
                payload = response.json()

            if self._settings.embedding_model not in _listed_model_ids(
                provider, payload
            ):
                return {
                    "provider": provider,
                    "url": self._base_url(provider),
                    "embedding_model": self._settings.embedding_model,
                    "status": "degraded",
                    "detail": "Configured embedding model is not listed by the model provider.",
                }

            return {
                "provider": provider,
                "url": self._base_url(provider),
                "embedding_model": self._settings.embedding_model,
                "status": "healthy",
            }
        except (
            httpx.HTTPError,
            ValueError,
        ) as exc:  # pragma: no cover - depends on local model service state
            return {
                "provider": provider,
                "url": self._base_url(provider),
                "embedding_model": self._settings.embedding_model,
                "status": "degraded",
                "detail": str(exc),
            }

    async def embed_query(self, query: str) -> list[float]:
        query = f"search_query: {query}"
        provider = self.provider
        if provider == "lmstudio":
            return await self._embed_lmstudio(query)
        if provider == "ollama":
            return await self._embed_ollama(query)

        return []

    async def _embed_ollama(self, query: str) -> list[float]:
        body = {
            "model": self._settings.embedding_model,
            "input": [query],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._ollama_url()}/api/embed", json=body
                )
                if response.status_code in {404, 405}:
                    return await self._embed_ollama_legacy(query, client)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError:
            return []

        embeddings = payload.get("embeddings") or []
        if not embeddings:
            return []

        return [float(value) for value in embeddings[0]]

    async def _embed_lmstudio(self, query: str) -> list[float]:
        body = {
            "model": self._settings.embedding_model,
            "input": [query],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._lm_studio_url()}/embeddings", json=body
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError:
            return []

        data = payload.get("data") or []
        if not data:
            return []

        first = min(data, key=lambda item: int(item.get("index") or 0))
        return [float(value) for value in first.get("embedding") or []]

    async def _embed_ollama_legacy(
        self, query: str, client: httpx.AsyncClient
    ) -> list[float]:
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

    def _ollama_url(self) -> str:
        return self._settings.ollama_url.rstrip("/")

    def _lm_studio_url(self) -> str:
        return self._settings.lm_studio_url.rstrip("/")

    def _base_url(self, provider: str) -> str:
        return self._lm_studio_url() if provider == "lmstudio" else self._ollama_url()

    def _health_url(self, provider: str) -> str:
        if provider == "lmstudio":
            return f"{self._lm_studio_url()}/models"

        return f"{self._ollama_url()}/api/tags"


def model_provider(provider: str) -> str:
    value = provider.casefold().strip()
    if value in {"lm-studio", "lm_studio"}:
        return "lmstudio"

    return value


def _listed_model_ids(provider: str, payload: Any) -> set[str]:
    if not isinstance(payload, dict):
        return set()

    if provider == "lmstudio":
        return {
            str(item.get("id"))
            for item in payload.get("data") or []
            if isinstance(item, dict) and item.get("id")
        }

    return {
        str(item.get("name") or item.get("model"))
        for item in payload.get("models") or []
        if isinstance(item, dict) and (item.get("name") or item.get("model"))
    }
