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


@lru_cache(maxsize=1)
def _turbopuffer_session_store() -> SessionStore:
  from src.db.session_store_turbopuffer import SessionStoreTurbopuffer
  return SessionStoreTurbopuffer()


@lru_cache(maxsize=1)
def _turbopuffer_working_memory_store() -> WorkingMemoryStore:
  from src.db.working_memory_store_turbopuffer import WorkingMemoryStoreTurbopuffer
  return WorkingMemoryStoreTurbopuffer()


class _DualWriteSessionStore(SessionStore):
  def __init__(self, primary: SessionStore, secondary: SessionStore):
    self._primary = primary
    self._secondary = secondary

  def get_session(self, session_id: str):
    return self._primary.get_session(session_id)

  def create_session(self, session_id: str, user_id: str, org_id: str | None, max_tokens: int):
    rec = self._primary.create_session(session_id, user_id, org_id, max_tokens)
    self._secondary.create_session(session_id, user_id, org_id, max_tokens)
    return rec

  def touch_session(self, session_id: str) -> None:
    self._primary.touch_session(session_id)
    self._secondary.touch_session(session_id)

  def update_total_tokens(self, session_id: str, new_total: int) -> None:
    self._primary.update_total_tokens(session_id, new_total)
    self._secondary.update_total_tokens(session_id, new_total)

  def increment_total_tokens(self, session_id: str, delta: int) -> None:
    self._primary.increment_total_tokens(session_id, delta)
    self._secondary.increment_total_tokens(session_id, delta)

  def count_all(self) -> int:
    return self._primary.count_all()


class _DualWriteWorkingMemoryStore(WorkingMemoryStore):
  def __init__(self, primary: WorkingMemoryStore, secondary: WorkingMemoryStore):
    self._primary = primary
    self._secondary = secondary

  def get_next_sequence_num(self, session_id: str) -> int:
    return self._primary.get_next_sequence_num(session_id)

  def insert_item(self, item):
    self._primary.insert_item(item)
    self._secondary.insert_item(item)

  def get_items_for_session(self, session_id: str, include_types=None):
    return self._primary.get_items_for_session(session_id, include_types=include_types)

  def count_items(self, session_id: str, pinned_only=None) -> int:
    return self._primary.count_items(session_id, pinned_only=pinned_only)

  def delete_items(self, session_id: str, pinned_only=None) -> None:
    self._primary.delete_items(session_id, pinned_only=pinned_only)
    self._secondary.delete_items(session_id, pinned_only=pinned_only)

  def sum_tokens(self, session_id: str) -> int:
    return self._primary.sum_tokens(session_id)

  def count_all(self) -> int:
    return self._primary.count_all()

  def sum_tokens_all(self) -> int:
    return self._primary.sum_tokens_all()

  def update_item_flags(self, item_id: str, session_id: str, pinned, relevance_score) -> None:
    self._primary.update_item_flags(item_id, session_id, pinned, relevance_score)
    self._secondary.update_item_flags(item_id, session_id, pinned, relevance_score)

  def eviction_candidates(self, session_id: str):
    return self._primary.eviction_candidates(session_id)

  def delete_item(self, item_id: str) -> None:
    self._primary.delete_item(item_id)
    self._secondary.delete_item(item_id)


def _session_store_for_backend(backend: str) -> SessionStore:
  if backend == "elastic":
    return _elastic_session_store()
  if backend == "clickhouse":
    return _clickhouse_session_store()
  if backend == "turbopuffer":
    return _turbopuffer_session_store()
  return _firebolt_session_store()


def _working_memory_store_for_backend(backend: str) -> WorkingMemoryStore:
  if backend == "elastic":
    return _elastic_working_memory_store()
  if backend == "clickhouse":
    return _clickhouse_working_memory_store()
  if backend == "turbopuffer":
    return _turbopuffer_working_memory_store()
  return _firebolt_working_memory_store()


def get_session_store() -> SessionStore:
  """
  Return a SessionStore for the active backend (Firebolt, Elasticsearch, or ClickHouse).
  """
  primary = _session_store_for_backend(config.vector_backend)
  if config.dual_write_backend:
    secondary = _session_store_for_backend(config.dual_write_backend)
    return _DualWriteSessionStore(primary=primary, secondary=secondary)
  return primary


def get_working_memory_store() -> WorkingMemoryStore:
  """
  Return a WorkingMemoryStore for the active backend (Firebolt, Elasticsearch, or ClickHouse).
  """
  primary = _working_memory_store_for_backend(config.vector_backend)
  if config.dual_write_backend:
    secondary = _working_memory_store_for_backend(config.dual_write_backend)
    return _DualWriteWorkingMemoryStore(primary=primary, secondary=secondary)
  return primary
