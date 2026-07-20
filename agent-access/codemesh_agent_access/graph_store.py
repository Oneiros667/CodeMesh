from __future__ import annotations

import re
import sys
from typing import Any

from .config import Settings

AsyncGraphDatabase: Any | None = None
_neo4j_import_attempted = False


class Neo4jGraphStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._neo4j_driver: Any | None = None

    async def close(self) -> None:
        driver = self._neo4j_driver
        self._neo4j_driver = None
        if driver is not None:
            await driver.close()

    async def health(self) -> dict[str, Any]:
        if _load_async_graph_database() is None:
            return {
                "uri": self._settings.neo4j_uri,
                "database": self._settings.neo4j_database,
                "status": "degraded",
                "detail": "The neo4j Python package is not installed.",
            }

        try:
            driver = self._neo4j()
            async with driver.session(
                database=self._settings.neo4j_database
            ) as session:
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

    async def get_node_properties(
        self, node_id: str, repository_id: str | None = None
    ) -> dict[str, Any] | None:
        if _load_async_graph_database() is None:
            return None

        try:
            driver = self._neo4j()
            async with driver.session(
                database=self._settings.neo4j_database
            ) as session:
                if repository_id:
                    result = await session.run(
                        "MATCH (n:CodeMeshNode {storageKey: $storage_key}) RETURN properties(n) AS node LIMIT 1",
                        storage_key=storage_key(repository_id, node_id),
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

    async def search_symbol_nodes(
        self,
        search_text: str,
        kinds: list[str],
        repository_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if _load_async_graph_database() is None or not kinds:
            return []

        try:
            driver = self._neo4j()
            async with driver.session(
                database=self._settings.neo4j_database
            ) as session:
                result = await session.run(
                    """
                    MATCH (n:CodeMeshNode)
                    WHERE
                        toLower(coalesce(n.kind, "")) IN $kinds
                        AND ($repository_id IS NULL OR n.repositoryId = $repository_id)
                        AND ($search_text = "" OR
                             toLower(coalesce(n.id, "")) CONTAINS $search_text OR
                             toLower(coalesce(n.stableKey, "")) CONTAINS $search_text OR
                             toLower(coalesce(n.name, "")) CONTAINS $search_text OR
                             toLower(coalesce(n.filePath, "")) CONTAINS $search_text OR
                             toLower(coalesce(n.metadataJson, "")) CONTAINS $search_text)
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

        return [dict(record["node"]) for record in records]

    async def get_relationship_properties(
        self,
        node_id: str,
        repository_id: str | None = None,
        depth: int = 1,
    ) -> list[dict[str, Any]]:
        if _load_async_graph_database() is None:
            return []

        clamped_depth = min(max(depth, 1), 4)
        if repository_id:
            query = f"""
            MATCH path = (:CodeMeshNode {{storageKey: $storage_key}})-[rels:CODEMESH_REL*1..{clamped_depth}]-()
            UNWIND rels AS relationship
            RETURN DISTINCT properties(relationship) AS relationship
            ORDER BY relationship.id
            """
            parameters = {"storage_key": storage_key(repository_id, node_id)}
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
            async with driver.session(
                database=self._settings.neo4j_database
            ) as session:
                result = await session.run(query, **parameters)
                records = await result.data()
        except Exception:
            return []

        return [dict(record["relationship"]) for record in records]

    async def get_context_candidates(
        self,
        node_id: str,
        repository_id: str | None = None,
        depth: int = 4,
    ) -> list[dict[str, Any]]:
        if _load_async_graph_database() is None:
            return []

        clamped_depth = min(max(depth, 1), 6)
        if repository_id:
            start_match = "MATCH (start:CodeMeshNode {storageKey: $storage_key})"
            parameters = {"storage_key": storage_key(repository_id, node_id)}
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
            async with driver.session(
                database=self._settings.neo4j_database
            ) as session:
                result = await session.run(query, **parameters)
                records = await result.data()
        except Exception:
            return []

        return [
            {
                "node": dict(record["node"]),
                "distance": int_value(record.get("distance")),
                "reason": str(record.get("reason") or "context"),
            }
            for record in records
            if record.get("node")
        ]

    async def get_primary_declaration_node(
        self,
        node_id: str,
        repository_id: str | None = None,
    ) -> dict[str, Any] | None:
        if _load_async_graph_database() is None or not node_id:
            return None

        if repository_id:
            symbol_match = "MATCH (symbol:CodeMeshNode {storageKey: $storage_key})"
            parameters = {"storage_key": storage_key(repository_id, node_id)}
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
            async with driver.session(
                database=self._settings.neo4j_database
            ) as session:
                result = await session.run(query, **parameters)
                record = await result.single()
        except Exception:
            return None

        return dict(record["node"]) if record else None

    async def get_context_relationship_records(
        self,
        node_id: str,
        repository_id: str | None = None,
        limit: int = 80,
    ) -> list[dict[str, Any]]:
        if _load_async_graph_database() is None or limit <= 0:
            return []

        if repository_id:
            node_match = "MATCH (node:CodeMeshNode {storageKey: $storage_key})"
            parameters = {
                "storage_key": storage_key(repository_id, node_id),
                "node_id": node_id,
                "limit": limit,
            }
        else:
            node_match = "MATCH (node:CodeMeshNode {id: $node_id})"
            parameters = {"node_id": node_id, "limit": limit}

        query = f"""
        {node_match}
        MATCH (node)-[relationship:CODEMESH_REL]-(other:CodeMeshNode)
        RETURN properties(relationship) AS relationship, properties(other) AS other
        ORDER BY
          CASE
            WHEN relationship.kind = 'Defines' THEN 0
            WHEN relationship.kind = 'Contains' AND relationship.targetNodeId = $node_id THEN 1
            WHEN relationship.kind = 'Invokes' AND relationship.targetNodeId = $node_id THEN 2
            WHEN relationship.kind = 'Invokes' AND relationship.sourceNodeId = $node_id THEN 3
            WHEN relationship.kind = 'Writes' THEN 4
            WHEN relationship.kind = 'Reads' THEN 5
            WHEN relationship.kind = 'UsesType' THEN 6
            WHEN relationship.kind = 'Returns' THEN 7
            WHEN relationship.kind IN ['Inherits', 'Implements', 'Overrides'] THEN 8
            WHEN relationship.kind = 'Contains' THEN 9
            ELSE 50
          END,
          coalesce(other.name, other.id, '')
        LIMIT $limit
        """

        try:
            driver = self._neo4j()
            async with driver.session(
                database=self._settings.neo4j_database
            ) as session:
                result = await session.run(query, **parameters)
                records = await result.data()
        except Exception:
            return []

        return [
            {
                "relationship": dict(record["relationship"]),
                "other": dict(record["other"]),
            }
            for record in records
        ]

    async def search_context_nodes(
        self,
        search_text: str,
        kinds: list[str],
        repository_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if _load_async_graph_database() is None:
            return []

        search_terms = lexical_terms(search_text)

        try:
            driver = self._neo4j()
            async with driver.session(
                database=self._settings.neo4j_database
            ) as session:
                result = await session.run(
                    """
                    MATCH (n:CodeMeshNode)
                    WITH n,
                         [term IN $search_terms WHERE any(value IN [
                             toLower(coalesce(n.id, "")),
                             toLower(coalesce(n.stableKey, "")),
                             toLower(coalesce(n.name, "")),
                             toLower(coalesce(n.filePath, ""))
                         ] WHERE value CONTAINS term)] AS matched_terms
                    WHERE
                        (size($search_terms) = 0 OR size(matched_terms) > 0)
                        AND (size($kinds) = 0 OR toLower(coalesce(n.kind, "")) IN $kinds)
                        AND ($repository_id IS NULL OR n.repositoryId = $repository_id)
                    RETURN properties(n) AS node
                    ORDER BY size(matched_terms) DESC,
                             CASE
                                 WHEN toLower(coalesce(n.name, "")) = $search_text THEN 0
                                 WHEN toLower(coalesce(n.name, "")) CONTAINS $search_text THEN 1
                                 WHEN toLower(coalesce(n.filePath, "")) CONTAINS $search_text THEN 2
                                 ELSE 3
                             END,
                             toLower(coalesce(n.filePath, "")),
                             toLower(coalesce(n.name, n.id, ""))
                    LIMIT $limit
                    """,
                    search_text=search_text,
                    search_terms=search_terms,
                    kinds=kinds,
                    repository_id=repository_id,
                    limit=limit,
                )
                records = await result.data()
        except Exception:
            return []

        return [dict(record["node"]) for record in records]

    async def delete_repository(self, repository_id: str) -> None:
        if _load_async_graph_database() is None or not repository_id:
            return

        driver = self._neo4j()
        async with driver.session(database=self._settings.neo4j_database) as session:
            result = await session.run(
                """
                MATCH ()-[r:CODEMESH_REL]->()
                WHERE r.repositoryId = $repository_id
                DELETE r
                """,
                repository_id=repository_id,
            )
            await result.consume()
            result = await session.run(
                """
                MATCH (n:CodeMeshNode)
                WHERE n.repositoryId = $repository_id
                DETACH DELETE n
                """,
                repository_id=repository_id,
            )
            await result.consume()

    def _neo4j(self) -> Any:
        graph_database = _load_async_graph_database()
        if graph_database is None:
            raise RuntimeError("The neo4j Python package is not installed.")

        if self._neo4j_driver is None:
            self._neo4j_driver = graph_database.driver(
                self._settings.neo4j_uri,
                auth=(self._settings.neo4j_user, self._settings.neo4j_password),
            )

        return self._neo4j_driver


def lexical_terms(search_text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"[a-z0-9]+", search_text.casefold())))


def _load_async_graph_database() -> Any | None:
    global AsyncGraphDatabase, _neo4j_import_attempted

    if AsyncGraphDatabase is not None or _neo4j_import_attempted:
        return AsyncGraphDatabase

    _neo4j_import_attempted = True
    try:
        if sys.platform.startswith("win"):
            return _load_async_graph_database_without_windows_wmi()

        from neo4j import AsyncGraphDatabase as loaded
    except (
        ImportError
    ):  # pragma: no cover - exercised only when dependencies are missing
        AsyncGraphDatabase = None
    else:
        AsyncGraphDatabase = loaded

    return AsyncGraphDatabase


def _load_async_graph_database_without_windows_wmi() -> Any | None:
    import platform

    original_system = platform.system
    original_release = platform.release
    original_machine = platform.machine
    try:
        platform.system = lambda: "Windows"
        platform.release = lambda: "unknown"
        platform.machine = lambda: "unknown"
        from neo4j import AsyncGraphDatabase as loaded
    except (
        ImportError
    ):  # pragma: no cover - exercised only when dependencies are missing
        return None
    finally:
        platform.system = original_system
        platform.release = original_release
        platform.machine = original_machine

    global AsyncGraphDatabase
    AsyncGraphDatabase = loaded
    return AsyncGraphDatabase


def storage_key(repository_id: str, node_id: str) -> str:
    return f"{repository_id}:{node_id}"


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
