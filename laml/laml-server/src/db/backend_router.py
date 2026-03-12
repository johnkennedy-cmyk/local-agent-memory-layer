"""Backend router for session and working-memory stores."""

from __future__ import annotations

from functools import lru_cache

from src.config import config
from src.db.session_store import SessionStore, FireboltSessionStore
from src.db.working_memory_store import WorkingMemoryStore, FireboltWorkingMemoryStore


@lru_cache(maxsize=1)
def _firebolt_session_store() -> SessionStore:
  return FireboltSessionStore()


@lru_cache(maxsize=1)
def _firebolt_working_memory_store() -> WorkingMemoryStore:
  return FireboltWorkingMemoryStore()


@lru_cache(maxsize=1)
def _elastic_session_store() -> SessionStore:
  from src.db.session_store_elastic import SessionStoreElastic
  return SessionStoreElastic()


@lru_cache(maxsize=1)
def _elastic_working_memory_store() -> WorkingMemoryStore:
  from src.db.working_memory_store_elastic import WorkingMemoryStoreElastic
  return WorkingMemoryStoreElastic()


@lru_cache(maxsize=1)
def _clickhouse_session_store() -> SessionStore:
  from src.db.session_store_clickhouse import SessionStoreClickHouse
  return SessionStoreClickHouse()


@lru_cache(maxsize=1)
def _clickhouse_working_memory_store() -> WorkingMemoryStore:
  from src.db.working_memory_store_clickhouse import WorkingMemoryStoreClickHouse
  return WorkingMemoryStoreClickHouse()


def get_session_store() -> SessionStore:
  """
  Return a SessionStore for the active backend (Firebolt, Elasticsearch, or ClickHouse).
  """
  backend = config.vector_backend
  if backend == "elastic":
    return _elastic_session_store()
  if backend == "clickhouse":
    return _clickhouse_session_store()
  return _firebolt_session_store()


def get_working_memory_store() -> WorkingMemoryStore:
  """
  Return a WorkingMemoryStore for the active backend (Firebolt, Elasticsearch, or ClickHouse).
  """
  backend = config.vector_backend
  if backend == "elastic":
    return _elastic_working_memory_store()
  if backend == "clickhouse":
    return _clickhouse_working_memory_store()
  return _firebolt_working_memory_store()

