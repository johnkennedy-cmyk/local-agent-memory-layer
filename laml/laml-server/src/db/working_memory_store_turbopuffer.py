"""Turbopuffer-backed working memory store (when vector backend=turbopuffer)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.config import config
from src.db.turbopuffer_client import TurbopufferClient
from src.db.working_memory_store import WorkingMemoryItem, WorkingMemoryStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _to_item(attrs: Dict[str, Any]) -> WorkingMemoryItem:
    return WorkingMemoryItem(
        item_id=str(attrs.get("item_id", "")),
        session_id=str(attrs.get("session_id", "")),
        user_id=str(attrs.get("user_id", "")),
        content_type=str(attrs.get("content_type", "message")),
        content=str(attrs.get("content", "")),
        token_count=int(attrs.get("token_count", 0)),
        pinned=bool(attrs.get("pinned", False)),
        relevance_score=float(attrs.get("relevance_score", 1.0)),
        sequence_num=int(attrs.get("sequence_num", 0)),
    )


def _wm_schema() -> Dict[str, Any]:
    return {
        "item_id": {"type": "string"},
        "session_id": {"type": "string"},
        "user_id": {"type": "string"},
        "content_type": {"type": "string"},
        "content": {"type": "string"},
        "token_count": {"type": "int"},
        "pinned": {"type": "bool"},
        "relevance_score": {"type": "float"},
        "sequence_num": {"type": "int"},
        "created_at": {"type": "string"},
        "last_accessed": {"type": "string"},
    }


class WorkingMemoryStoreTurbopuffer(WorkingMemoryStore):
    """Working memory persistence in a Turbopuffer namespace."""

    def __init__(self):
        self._client = TurbopufferClient()
        self._namespace = config.turbopuffer.working_memory_namespace

    def _query(
        self,
        *,
        filters: Optional[List[Any]] = None,
        include_attributes: Optional[List[str]] = None,
        top_k: int = 10000,
    ) -> List[Dict[str, Any]]:
        resp = self._client.query(
            self._namespace,
            rank_by=["id", "asc"],
            top_k=top_k,
            filters=filters,
            include_attributes=include_attributes,
        )
        out: List[Dict[str, Any]] = []
        for row in resp.get("rows", []):
            attrs = row.get("attributes") if isinstance(row, dict) else None
            if isinstance(attrs, dict):
                merged = dict(attrs)
                if "id" in row and "item_id" not in merged:
                    merged["item_id"] = row["id"]
                out.append(merged)
            else:
                out.append(dict(row))
        return out

    def _upsert_attrs(self, attrs: Dict[str, Any]) -> None:
        row = dict(attrs)
        row["id"] = str(attrs["item_id"])
        self._client.write(
            self._namespace,
            upsert_rows=[row],
            schema=_wm_schema(),
        )

    def get_next_sequence_num(self, session_id: str) -> int:
        rows = self._query(
            filters=["session_id", "Eq", session_id],
            include_attributes=["sequence_num"],
        )
        if not rows:
            return 1
        return max(int(row.get("sequence_num", 0)) for row in rows) + 1

    def insert_item(self, item: WorkingMemoryItem) -> None:
        now = _now_iso()
        self._upsert_attrs(
            {
                "item_id": item.item_id,
                "session_id": item.session_id,
                "user_id": item.user_id,
                "content_type": item.content_type,
                "content": item.content,
                "token_count": int(item.token_count),
                "pinned": bool(item.pinned),
                "relevance_score": float(item.relevance_score),
                "sequence_num": int(item.sequence_num),
                "created_at": now,
                "last_accessed": now,
            }
        )

    def get_items_for_session(
        self,
        session_id: str,
        include_types: Optional[List[str]] = None,
    ) -> List[WorkingMemoryItem]:
        rows = self._query(
            filters=["session_id", "Eq", session_id],
            include_attributes=[
                "item_id",
                "session_id",
                "user_id",
                "content_type",
                "content",
                "token_count",
                "pinned",
                "relevance_score",
                "sequence_num",
            ],
        )
        if include_types:
            rows = [row for row in rows if row.get("content_type") in include_types]
        items = [_to_item(row) for row in rows]
        items.sort(key=lambda i: (not i.pinned, -i.relevance_score, -i.sequence_num))
        return items

    def count_items(
        self,
        session_id: str,
        pinned_only: Optional[bool] = None,
    ) -> int:
        rows = self._query(filters=["session_id", "Eq", session_id], include_attributes=["pinned"])
        if pinned_only is None:
            return len(rows)
        return sum(1 for row in rows if bool(row.get("pinned", False)) == pinned_only)

    def delete_items(
        self,
        session_id: str,
        pinned_only: Optional[bool] = None,
    ) -> None:
        rows = self._query(
            filters=["session_id", "Eq", session_id],
            include_attributes=["item_id", "pinned"],
        )
        ids = []
        for row in rows:
            if pinned_only is None or bool(row.get("pinned", False)) == pinned_only:
                ids.append(str(row.get("item_id")))
        if ids:
            self._client.write(self._namespace, deletes=ids)

    def sum_tokens(self, session_id: str) -> int:
        rows = self._query(filters=["session_id", "Eq", session_id], include_attributes=["token_count"])
        return sum(int(row.get("token_count", 0)) for row in rows)

    def count_all(self) -> int:
        rows = self._query(include_attributes=["item_id"])
        return len(rows)

    def sum_tokens_all(self) -> int:
        rows = self._query(include_attributes=["token_count"])
        return sum(int(row.get("token_count", 0)) for row in rows)

    def update_item_flags(
        self,
        item_id: str,
        session_id: str,
        pinned: Optional[bool],
        relevance_score: Optional[float],
    ) -> None:
        rows = self._query(
            filters=["And", [["item_id", "Eq", item_id], ["session_id", "Eq", session_id]]],
            include_attributes=[
                "item_id",
                "session_id",
                "user_id",
                "content_type",
                "content",
                "token_count",
                "pinned",
                "relevance_score",
                "sequence_num",
                "created_at",
            ],
            top_k=1,
        )
        if not rows:
            return
        attrs = rows[0]
        if pinned is not None:
            attrs["pinned"] = bool(pinned)
        if relevance_score is not None:
            attrs["relevance_score"] = float(relevance_score)
        attrs["last_accessed"] = _now_iso()
        self._upsert_attrs(attrs)

    def eviction_candidates(self, session_id: str) -> List[Tuple[str, int, float]]:
        rows = self._query(
            filters=["session_id", "Eq", session_id],
            include_attributes=["item_id", "token_count", "relevance_score", "sequence_num", "pinned"],
        )
        non_pinned = [row for row in rows if not bool(row.get("pinned", False))]
        non_pinned.sort(key=lambda row: (float(row.get("relevance_score", 0)), int(row.get("sequence_num", 0))))
        return [
            (
                str(row.get("item_id")),
                int(row.get("token_count", 0)),
                float(row.get("relevance_score", 0)),
            )
            for row in non_pinned
        ]

    def delete_item(self, item_id: str) -> None:
        self._client.write(self._namespace, deletes=[str(item_id)])
