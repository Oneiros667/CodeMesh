from __future__ import annotations

from functools import lru_cache

from .config import Settings
from .store import CodeMeshReadStore


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


@lru_cache(maxsize=1)
def get_store() -> CodeMeshReadStore:
    return CodeMeshReadStore(get_settings())
