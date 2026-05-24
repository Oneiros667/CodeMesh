from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    mongo_uri: str
    mongo_database: str
    mongo_content_collection: str
    qdrant_url: str
    qdrant_collection: str
    model_provider: str
    ollama_url: str
    embedding_model: str

    @classmethod
    def from_env(cls) -> "Settings":
        neo4j_user, neo4j_password = _neo4j_credentials()

        return cls(
            host=os.getenv("CODEMESH_AGENT_HOST", "0.0.0.0"),
            port=int(os.getenv("CODEMESH_AGENT_PORT", "8080")),
            neo4j_uri=os.getenv("CODEMESH_NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_database=os.getenv("CODEMESH_NEO4J_DATABASE", "neo4j"),
            mongo_uri=os.getenv("CODEMESH_MONGO_URI", "mongodb://localhost:27017"),
            mongo_database=os.getenv("CODEMESH_MONGO_DATABASE", "codemesh"),
            mongo_content_collection=os.getenv("CODEMESH_MONGO_CONTENT_COLLECTION", "content"),
            qdrant_url=os.getenv("CODEMESH_QDRANT_URL", "http://localhost:6333"),
            qdrant_collection=os.getenv("CODEMESH_QDRANT_COLLECTION", "codemesh-code"),
            model_provider=os.getenv("CODEMESH_MODEL_PROVIDER", "none"),
            ollama_url=os.getenv("CODEMESH_OLLAMA_URL", "http://localhost:11434"),
            embedding_model=os.getenv("CODEMESH_EMBEDDING_MODEL", "nomic-embed-text:latest"),
        )


def _neo4j_credentials() -> tuple[str, str]:
    user = os.getenv("CODEMESH_NEO4J_USER")
    password = os.getenv("CODEMESH_NEO4J_PASSWORD")
    if user and password:
        return user, password

    auth = os.getenv("CODEMESH_NEO4J_AUTH", "neo4j/codemesh")
    if "/" in auth:
        auth_user, auth_password = auth.split("/", 1)
        return user or auth_user, password or auth_password

    return user or "neo4j", password or "codemesh"
