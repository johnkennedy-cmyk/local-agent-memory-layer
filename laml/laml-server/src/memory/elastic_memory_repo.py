"""Elasticsearch-backed repository for long-term memory documents (when vector backend=elastic)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config import config


def _get_es_client():
    from elasticsearch import Elasticsearch

    es_config = config.elastic
    kwargs = {
        "hosts": [es_config.url],
        "verify_certs": es_config.ssl_verify,
    }
    if es_config.api_key:
        kwargs["api_key"] = es_config.api_key
    elif es_config.username and es_config.password:
        kwargs["basic_auth"] = (es_config.username, es_config.password)
    return Elasticsearch(**kwargs)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _doc_to_row(doc: Dict[str, Any], id_: str) -> Dict[str, Any]:
    """Convert ES document to a row-like dict (keys matching SQL column names)."""
    row = dict(doc)
    row["memory_id"] = row.get("memory_id") or id_
    # Ensure entities is list for compatibility
    if "entities" in row and isinstance(row["entities"], str):
        row["entities"] = [e.strip() for e in row["entities"].split(",") if e.strip()]
    return row


class ElasticMemoryRepository:
    """
    Long-term memory CRUD against a single Elasticsearch index.

    Used when LAML_VECTOR_BACKEND=elastic. Same index as ElasticVectorStore.
    """

    def __init__(self):
        self._client = _get_es_client()
        self._index = config.elastic.index_name

    def insert(self, doc: Dict[str, Any]) -> None:
        """Index a full long-term memory document. Id = doc['memory_id']."""
        memory_id = doc["memory_id"]
        now = _now_iso()
        body = dict(doc)
        body.setdefault("created_at", now)
        body.setdefault("updated_at", now)
        body.setdefault("last_accessed", now)
        body.setdefault("access_count", 0)
        body.setdefault("confidence", 1.0)
        body.setdefault("decay_factor", 1.0)
        if "embedding" in body:
            body["embedding"] = list(body["embedding"])
        self._client.index(
            index=self._index,
            id=memory_id,
            document=body,
            refresh=True,
        )

    def update(self, memory_id: str, user_id: str, fields: Dict[str, Any]) -> None:
        """Partial update; verifies user_id matches."""
        doc = self._client.get(index=self._index, id=memory_id, source=True)
        if not doc.get("found"):
            return
        src = doc["_source"]
        if src.get("user_id") != user_id:
            return
        updates = dict(fields)
        updates["updated_at"] = _now_iso()
        if "embedding" in updates:
            updates["embedding"] = list(updates["embedding"])
        self._client.update(
            index=self._index,
            id=memory_id,
            body={"doc": updates},
            refresh=True,
        )

    def get_by_id(
        self, memory_id: str, user_id: Optional[str] = None, include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Return one document as row-like dict or None."""
        try:
            doc = self._client.get(index=self._index, id=memory_id, source=True)
        except Exception:
            return None
        if not doc.get("found"):
            return None
        src = doc["_source"]
        if not include_deleted and src.get("deleted_at"):
            return None
        if user_id is not None and src.get("user_id") != user_id:
            return None
        return _doc_to_row(src, memory_id)

    def get_many_by_ids(
        self, ids: List[str], user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return documents for given ids; excludes soft-deleted; optional user filter."""
        if not ids:
            return []
        resp = self._client.mget(
            index=self._index,
            body={"ids": ids},
            _source=True,
        )
        rows = []
        for d in resp.get("docs", []):
            if not d.get("found"):
                continue
            src = d["_source"]
            if src.get("deleted_at"):
                continue
            if user_id is not None and src.get("user_id") != user_id:
                continue
            rows.append(_doc_to_row(src, d["_id"]))
        return rows

    def count_for_user(self, user_id: str, include_deleted: bool = False) -> int:
        """Count documents for user; optionally include soft-deleted."""
        q = {"term": {"user_id": user_id}}
        if not include_deleted:
            q = {"bool": {"must": [q, {"bool": {"must_not": {"exists": {"field": "deleted_at"}}}}]}}
        resp = self._client.count(index=self._index, body={"query": q})
        return int(resp.get("count", 0))

    def soft_delete(self, memory_id: str, user_id: str) -> None:
        """Set deleted_at; only if user_id matches."""
        doc = self.get_by_id(memory_id, user_id=user_id, include_deleted=True)
        if not doc:
            return
        self._client.update(
            index=self._index,
            id=memory_id,
            body={"doc": {"deleted_at": _now_iso()}},
            refresh=True,
        )

    def hard_delete(self, memory_id: str, user_id: str) -> None:
        """Permanently delete document if user_id matches."""
        doc = self.get_by_id(memory_id, user_id=user_id, include_deleted=True)
        if not doc:
            return
        self._client.delete(index=self._index, id=memory_id, refresh=True)

    def delete_all_for_user(self, user_id: str) -> None:
        """Delete all documents for user (used by forget_all_user_memories)."""
        self._client.delete_by_query(
            index=self._index,
            body={"query": {"term": {"user_id": user_id}}},
            refresh=True,
        )

    def count_total(self, include_deleted: bool = False) -> int:
        q = {"match_all": {}}
        if not include_deleted:
            q = {"bool": {"must_not": {"exists": {"field": "deleted_at"}}}}
        resp = self._client.count(index=self._index, body={"query": q})
        return int(resp.get("count", 0))

    def increment_access_count(self, memory_id: str) -> None:
        """Increment access_count and set last_accessed."""
        self._client.update(
            index=self._index,
            id=memory_id,
            body={
                "script": {
                    "source": "ctx._source.access_count = (ctx._source.access_count != null ? ctx._source.access_count : 0) + 1; ctx._source.last_accessed = params.now;",
                    "lang": "painless",
                    "params": {"now": _now_iso()},
                }
            },
            refresh=True,
        )
