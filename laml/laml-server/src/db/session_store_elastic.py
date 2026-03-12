"""Elasticsearch-backed session store (when vector backend=elastic)."""

from __future__ import annotations

from datetime import datetime, timezone

from src.config import config
from src.db.session_store import SessionStore, SessionRecord


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


class SessionStoreElastic(SessionStore):
    """Elasticsearch-backed session store using laml_sessions index."""

    def __init__(self):
        self._client = _get_es_client()
        self._index = config.elastic.sessions_index

    def get_session(self, session_id: str) -> SessionRecord | None:
        try:
            doc = self._client.get(index=self._index, id=session_id, source=True)
        except Exception:
            return None
        if not doc.get("found"):
            return None
        src = doc["_source"]
        return SessionRecord(
            session_id=session_id,
            user_id=src.get("user_id", ""),
            org_id=src.get("org_id"),
            total_tokens=int(src.get("total_tokens", 0)),
            max_tokens=int(src.get("max_tokens", 8000)),
        )

    def create_session(
        self,
        session_id: str,
        user_id: str,
        org_id: str | None,
        max_tokens: int,
    ) -> SessionRecord:
        now = _now_iso()
        body = {
            "session_id": session_id,
            "user_id": user_id,
            "org_id": org_id,
            "total_tokens": 0,
            "max_tokens": max_tokens,
            "created_at": now,
            "last_activity": now,
        }
        self._client.index(
            index=self._index,
            id=session_id,
            document=body,
            refresh=True,
        )
        return SessionRecord(
            session_id=session_id,
            user_id=user_id,
            org_id=org_id,
            total_tokens=0,
            max_tokens=max_tokens,
        )

    def touch_session(self, session_id: str) -> None:
        self._client.update(
            index=self._index,
            id=session_id,
            body={"doc": {"last_activity": _now_iso()}},
            refresh=True,
        )

    def update_total_tokens(self, session_id: str, new_total: int) -> None:
        self._client.update(
            index=self._index,
            id=session_id,
            body={"doc": {"total_tokens": new_total}},
            refresh=True,
        )

    def increment_total_tokens(self, session_id: str, delta: int) -> None:
        self._client.update(
            index=self._index,
            id=session_id,
            body={
                "script": {
                    "source": "ctx._source.total_tokens += params.delta; ctx._source.last_activity = params.now;",
                    "lang": "painless",
                    "params": {"delta": delta, "now": _now_iso()},
                }
            },
            refresh=True,
        )

    def count_all(self) -> int:
        resp = self._client.count(index=self._index, body={"query": {"match_all": {}}})
        return int(resp.get("count", 0))
