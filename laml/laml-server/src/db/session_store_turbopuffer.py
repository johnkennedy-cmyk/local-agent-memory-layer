"""Turbopuffer-backed session store (when vector backend=turbopuffer)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.config import config
from src.db.session_store import SessionRecord, SessionStore
from src.db.turbopuffer_client import TurbopufferClient


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _session_schema() -> Dict[str, Any]:
    return {
        "session_id": {"type": "string"},
        "user_id": {"type": "string"},
        "org_id": {"type": "string"},
        "total_tokens": {"type": "int"},
        "max_tokens": {"type": "int"},
        "created_at": {"type": "string"},
        "last_activity": {"type": "string"},
    }


class SessionStoreTurbopuffer(SessionStore):
    """Session persistence in a Turbopuffer namespace."""

    def __init__(self):
        self._client = TurbopufferClient()
        self._namespace = config.turbopuffer.sessions_namespace

    def _upsert(self, row: Dict[str, Any]) -> None:
        self._client.write(
            self._namespace,
            upsert_rows=[row],
            schema=_session_schema(),
        )

    def _fetch_one(self, session_id: str) -> Optional[Dict[str, Any]]:
        resp = self._client.query(
            self._namespace,
            rank_by=["id", "asc"],
            top_k=1,
            filters=["session_id", "Eq", session_id],
            include_attributes=[
                "session_id",
                "user_id",
                "org_id",
                "total_tokens",
                "max_tokens",
                "created_at",
                "last_activity",
            ],
        )
        rows = resp.get("rows", [])
        if not rows:
            return None
        return rows[0].get("attributes") or {}

    def get_session(self, session_id: str) -> SessionRecord | None:
        rec = self._fetch_one(session_id)
        if rec is None:
            return None
        return SessionRecord(
            session_id=session_id,
            user_id=str(rec.get("user_id", "")),
            org_id=rec.get("org_id"),
            total_tokens=int(rec.get("total_tokens", 0)),
            max_tokens=int(rec.get("max_tokens", 8000)),
        )

    def create_session(
        self,
        session_id: str,
        user_id: str,
        org_id: str | None,
        max_tokens: int,
    ) -> SessionRecord:
        now = _now_iso()
        self._upsert(
            {
                "id": str(session_id),
                "session_id": str(session_id),
                "user_id": str(user_id),
                "org_id": org_id,
                "total_tokens": 0,
                "max_tokens": int(max_tokens),
                "created_at": now,
                "last_activity": now,
            }
        )
        return SessionRecord(
            session_id=session_id,
            user_id=user_id,
            org_id=org_id,
            total_tokens=0,
            max_tokens=max_tokens,
        )

    def touch_session(self, session_id: str) -> None:
        rec = self._fetch_one(session_id)
        if rec is None:
            return
        rec["last_activity"] = _now_iso()
        rec["id"] = str(session_id)
        self._upsert(rec)

    def update_total_tokens(self, session_id: str, new_total: int) -> None:
        rec = self._fetch_one(session_id)
        if rec is None:
            return
        rec["total_tokens"] = int(new_total)
        rec["id"] = str(session_id)
        self._upsert(rec)

    def increment_total_tokens(self, session_id: str, delta: int) -> None:
        rec = self._fetch_one(session_id)
        if rec is None:
            return
        rec["total_tokens"] = int(rec.get("total_tokens", 0)) + int(delta)
        rec["last_activity"] = _now_iso()
        rec["id"] = str(session_id)
        self._upsert(rec)

    def count_all(self) -> int:
        resp = self._client.query(
            self._namespace,
            rank_by=["id", "asc"],
            top_k=10000,
        )
        return len(resp.get("rows", []))
