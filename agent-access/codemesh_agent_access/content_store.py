from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from .config import Settings
from .models import (
    IngestionRunListResponse,
    IngestionRunSummary,
    RepositoryListResponse,
    RepositorySummary,
)

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError:  # pragma: no cover - exercised only when dependencies are missing
    MongoClient = None  # type: ignore[assignment]
    PyMongoError = Exception  # type: ignore[assignment]


class MongoContentStore:
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

    async def get_content(self, content_hash: str) -> dict[str, Any] | None:
        if not content_hash or MongoClient is None:
            return None

        def find_one() -> dict[str, Any] | None:
            collection = self._mongo()[self._settings.mongo_database][
                self._settings.mongo_content_collection
            ]
            document = collection.find_one({"_id": content_hash})
            return dict(document) if document else None

        try:
            document = await asyncio.to_thread(find_one)
        except PyMongoError:
            return None

        return normalize_content(document) if document else None

    async def list_repositories(self, limit: int = 50) -> RepositoryListResponse:
        if MongoClient is None:
            return RepositoryListResponse()

        collection = self._mongo()[self._settings.mongo_database][
            self._settings.mongo_repositories_collection
        ]
        documents = await asyncio.to_thread(
            lambda: list(
                collection.find({})
                .sort("lastSeenAtUtc", -1)
                .limit(max(1, min(limit, 500)))
            )
        )

        return RepositoryListResponse(
            repositories=[normalize_repository(document) for document in documents]
        )

    async def get_repository(self, repository_id: str) -> RepositorySummary | None:
        if MongoClient is None:
            return None

        collection = self._mongo()[self._settings.mongo_database][
            self._settings.mongo_repositories_collection
        ]
        document = await asyncio.to_thread(
            find_repository_document, collection, repository_id
        )
        return normalize_repository(document) if document else None

    async def delete_repository(self, repository_id: str) -> None:
        if not repository_id or MongoClient is None:
            return

        def delete() -> None:
            database = self._mongo()[self._settings.mongo_database]
            content_collection = database[self._settings.mongo_content_collection]
            repository_collection = database[
                self._settings.mongo_repositories_collection
            ]
            runs_collection = database[self._settings.mongo_ingestion_runs_collection]

            content_collection.update_many(
                {"repositoryIds": repository_id},
                {
                    "$pull": {"repositoryIds": repository_id},
                    "$unset": {
                        f"repositoryRuns.{repository_id}": "",
                        f"repositoryLastSeenAtUtc.{repository_id}": "",
                    },
                },
            )
            content_collection.delete_many({"repositoryIds": {"$size": 0}})
            repository_collection.delete_one({"_id": repository_id})
            runs_collection.delete_many({"repositoryId": repository_id})

        await asyncio.to_thread(delete)

    async def list_ingestion_runs(
        self,
        repository_id: str | None = None,
        limit: int = 50,
    ) -> IngestionRunListResponse:
        if MongoClient is None:
            return IngestionRunListResponse()

        repository_id = await self.resolve_repository_id(repository_id)
        filter_query = {"repositoryId": repository_id} if repository_id else {}
        collection = self._mongo()[self._settings.mongo_database][
            self._settings.mongo_ingestion_runs_collection
        ]
        documents = await asyncio.to_thread(
            lambda: list(
                collection.find(filter_query)
                .sort("startedAtUtc", -1)
                .limit(max(1, min(limit, 500)))
            )
        )

        return IngestionRunListResponse(
            runs=[normalize_ingestion_run(document) for document in documents]
        )

    async def resolve_repository_id(self, repository_id: str | None) -> str | None:
        if not repository_id:
            return None

        try:
            repository = await self.get_repository(repository_id)
        except PyMongoError:
            return repository_id

        return repository.repository_id if repository else repository_id

    def _mongo(self) -> Any:
        if MongoClient is None:
            raise RuntimeError("The pymongo package is not installed.")

        if self._mongo_client is None:
            self._mongo_client = MongoClient(
                self._settings.mongo_uri, serverSelectionTimeoutMS=2000
            )

        return self._mongo_client


def find_repository_document(
    collection: Any, repository_id: str
) -> dict[str, Any] | None:
    exact = collection.find_one({"_id": repository_id})
    if exact is not None:
        return exact

    aliases = sorted({repository_id, repository_alias(repository_id)})
    documents = list(
        collection.find(
            {
                "$or": [
                    {"alias": {"$in": aliases}},
                    {"metadata.alias": {"$in": aliases}},
                ]
            }
        ).limit(3)
    )
    by_repository_id = {
        str(document.get("_id") or document.get("repositoryId") or ""): document
        for document in documents
    }
    if len(by_repository_id) > 1:
        raise RuntimeError(
            f"Repository alias '{repository_id}' matches multiple repositories."
        )

    return next(iter(by_repository_id.values()), None)


def normalize_content(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "hash": str(document.get("_id") or document.get("hash") or ""),
        "text": str(document.get("text") or ""),
        "media_type": str(document.get("mediaType") or ""),
        "created_at": datetime_value(document.get("createdAtUtc")),
        "updated_at": datetime_value(document.get("updatedAtUtc")),
    }


def normalize_repository(document: dict[str, Any]) -> RepositorySummary:
    metadata = string_dict(document.get("metadata"))
    return RepositorySummary(
        repository_id=str(document.get("_id") or document.get("repositoryId") or ""),
        alias=optional_str(document.get("alias")) or metadata.get("alias"),
        root_path=str(document.get("rootPath") or ""),
        remote_url=optional_str(document.get("remoteUrl")),
        branch=optional_str(document.get("branch")),
        commit=optional_str(document.get("commit")),
        first_seen_at=datetime_value(document.get("firstSeenAtUtc")),
        last_seen_at=datetime_value(document.get("lastSeenAtUtc")),
        last_run_id=optional_str(document.get("lastRunId")),
        last_stage=optional_str(document.get("lastStage")),
        last_message=optional_str(document.get("lastMessage")),
        node_count=int_value(document.get("nodeCount")),
        relationship_count=int_value(document.get("relationshipCount")),
        content_count=int_value(document.get("contentCount")),
        embedding_count=optional_int(document.get("embeddingCount")),
        metadata=metadata,
    )


def normalize_ingestion_run(document: dict[str, Any]) -> IngestionRunSummary:
    return IngestionRunSummary(
        run_id=str(document.get("_id") or document.get("runId") or ""),
        repository_id=str(document.get("repositoryId") or ""),
        repository_root=str(document.get("repositoryRoot") or ""),
        stage=str(document.get("stage") or ""),
        started_at=datetime_value(document.get("startedAtUtc")),
        finished_at=datetime_value(document.get("finishedAtUtc")),
        message=optional_str(document.get("message")),
        language=str(document.get("language") or ""),
        parser_name=str(document.get("parserName") or ""),
        solution_path=optional_str(document.get("solutionPath")),
        project_path=optional_str(document.get("projectPath")),
        dry_run=bool(document.get("dryRun") or False),
        skip_embeddings=bool(
            document.get("skipEmbeddings")
            if document.get("skipEmbeddings") is not None
            else True
        ),
        embedding_provider=str(document.get("embeddingProvider") or ""),
        embedding_model=str(document.get("embeddingModel") or ""),
        node_count=int_value(document.get("nodeCount")),
        relationship_count=int_value(document.get("relationshipCount")),
        content_count=int_value(document.get("contentCount")),
        embedding_count=int_value(document.get("embeddingCount")),
        stats=normalize_stats(document.get("stats")),
        diagnostic_count=int_value(document.get("diagnosticCount")),
        error_diagnostic_count=int_value(document.get("errorDiagnosticCount")),
        warning_diagnostic_count=int_value(document.get("warningDiagnosticCount")),
        metadata=string_dict(document.get("metadata")),
    )


def normalize_stats(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    return {
        "parsed_node_count": int_value(
            value.get("ParsedNodeCount") or value.get("parsedNodeCount")
        ),
        "written_node_count": int_value(
            value.get("WrittenNodeCount") or value.get("writtenNodeCount")
        ),
        "skipped_node_count": int_value(
            value.get("SkippedNodeCount") or value.get("skippedNodeCount")
        ),
        "parsed_relationship_count": int_value(
            value.get("ParsedRelationshipCount") or value.get("parsedRelationshipCount")
        ),
        "written_relationship_count": int_value(
            value.get("WrittenRelationshipCount")
            or value.get("writtenRelationshipCount")
        ),
        "skipped_relationship_count": int_value(
            value.get("SkippedRelationshipCount")
            or value.get("skippedRelationshipCount")
        ),
        "parsed_content_count": int_value(
            value.get("ParsedContentCount") or value.get("parsedContentCount")
        ),
        "written_content_count": int_value(
            value.get("WrittenContentCount") or value.get("writtenContentCount")
        ),
        "skipped_content_count": int_value(
            value.get("SkippedContentCount") or value.get("skippedContentCount")
        ),
        "written_embedding_count": int_value(
            value.get("WrittenEmbeddingCount") or value.get("writtenEmbeddingCount")
        ),
        "skipped_embedding_count": int_value(
            value.get("SkippedEmbeddingCount") or value.get("skippedEmbeddingCount")
        ),
        "summary_candidate_count": int_value(
            value.get("SummaryCandidateCount") or value.get("summaryCandidateCount")
        ),
        "written_summary_count": int_value(
            value.get("WrittenSummaryCount") or value.get("writtenSummaryCount")
        ),
        "skipped_summary_count": int_value(
            value.get("SkippedSummaryCount") or value.get("skippedSummaryCount")
        ),
        "failed_summary_count": int_value(
            value.get("FailedSummaryCount") or value.get("failedSummaryCount")
        ),
    }


def datetime_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def optional_str(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value)
    return text if text else None


def optional_int(value: Any) -> int | None:
    if value is None:
        return None

    return int_value(value)


def repository_alias(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "repository"

    parts: list[str] = []
    previous_was_separator = True
    for index, character in enumerate(text):
        if not character.isalnum():
            if not previous_was_separator and parts:
                parts.append("_")
            previous_was_separator = True
            continue

        if should_split_alias_word(text, index) and not previous_was_separator:
            parts.append("_")

        parts.append(character.lower())
        previous_was_separator = False

    alias = "".join(parts).strip("_")
    return alias or "repository"


def should_split_alias_word(value: str, index: int) -> bool:
    character = value[index]
    if not character.isupper() or index == 0:
        return False

    previous = value[index - 1]
    next_character = value[index + 1] if index + 1 < len(value) else ""

    return (
        previous.islower()
        or previous.isdigit()
        or (previous.isupper() and bool(next_character) and next_character.islower())
    )


def string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    return {str(key): str(item) for key, item in value.items()}


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
