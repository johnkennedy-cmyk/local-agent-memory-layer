"""Turbopuffer-backed long-term memory repository."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from src.config import config
from src.db.turbopuffer_client import TurbopufferClient


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _normalize_string_array(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v)]
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.startswith("{") and cleaned.endswith("}"):
            cleaned = cleaned[1:-1]
        if not cleaned:
            return []
        return [part.strip() for part in cleaned.split(",") if part.strip()]
    return [str(value)]


def _ltm_schema() -> Dict[str, Any]:
    dims = int(config.turbopuffer.embedding_dimensions or 768)
    return {
        "vector": {"type": f"[{dims}]f32", "ann": True},
        "memory_id": {"type": "string"},
        "user_id": {"type": "string"},
        "memory_category": {"type": "string"},
        "memory_subtype": {"type": "string"},
        "content": {"type": "string"},
        "summary": {"type": "string"},
        "entities": {"type": "[]string"},
        "importance": {"type": "float"},
        "event_time": {"type": "string"},
        "metadata": {"type": "string"},
        "is_temporal": {"type": "int"},
        "source_session": {"type": "string"},
        "source_type": {"type": "string"},
        "access_count": {"type": "int"},
        "created_at": {"type": "string"},
        "last_accessed": {"type": "string"},
        "updated_at": {"type": "string"},
        "deleted": {"type": "int"},
        "deleted_at": {"type": "string"},
    }


class TurbopufferMemoryRepository:
    """Long-term memory CRUD against a Turbopuffer namespace."""

    def __init__(self):
        self._client = TurbopufferClient()
        self._namespace = config.turbopuffer.long_term_namespace

    def _row_from_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(doc["memory_id"]),
            "vector": list(doc.get("embedding") or []),
            "memory_id": str(doc["memory_id"]),
            "user_id": str(doc["user_id"]),
            "memory_category": doc.get("memory_category", "semantic"),
            "memory_subtype": doc.get("memory_subtype", "domain"),
            "content": doc.get("content", ""),
            "summary": doc.get("summary"),
            "entities": _normalize_string_array(doc.get("entities")),
            "importance": float(doc.get("importance", 0.5)),
            "event_time": doc.get("event_time"),
            "metadata": "" if doc.get("metadata") is None else str(doc.get("metadata")),
            "is_temporal": 1 if doc.get("is_temporal") else 0,
            "source_session": doc.get("source_session"),
            "source_type": doc.get("source_type", "conversation"),
            "access_count": int(doc.get("access_count", 0)),
            "created_at": doc.get("created_at") or _now_iso(),
            "last_accessed": doc.get("last_accessed") or _now_iso(),
            "updated_at": doc.get("updated_at") or _now_iso(),
            "deleted": 1 if doc.get("deleted_at") else 0,
            "deleted_at": doc.get("deleted_at"),
        }

    def _fetch_one_by_filter(self, filter_expr: List[Any]) -> Optional[Dict[str, Any]]:
        resp = self._client.query(
            self._namespace,
            rank_by=["id", "asc"],
            top_k=1,
            filters=filter_expr,
            include_attributes=[
                "vector",
                "memory_id",
                "user_id",
                "memory_category",
                "memory_subtype",
                "content",
                "summary",
                "entities",
                "importance",
                "access_count",
                "created_at",
                "metadata",
                "deleted",
                "deleted_at",
                "event_time",
                "is_temporal",
                "source_session",
                "source_type",
                "updated_at",
                "last_accessed",
            ],
        )
        rows = resp.get("rows", [])
        if not rows:
            return None
        row = rows[0]
        attrs = row.get("attributes") if isinstance(row, dict) else None
        if not isinstance(attrs, dict):
            attrs = dict(row)
        return {
            "id": str(row.get("id")),
            "embedding": attrs.get("vector") or [],
            **attrs,
        }

    def _fetch_many_by_ids(self, ids: List[str], user_id: Optional[str]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for memory_id in ids:
            predicates: List[List[Any]] = [["memory_id", "Eq", memory_id], ["deleted", "Eq", 0]]
            if user_id is not None:
                predicates.append(["user_id", "Eq", user_id])
            rec = self._fetch_one_by_filter(["And", predicates] if len(predicates) > 1 else predicates[0])
            if rec:
                out.append(rec)
        return out

    def insert(self, doc: Dict[str, Any]) -> None:
        self._client.write(
            self._namespace,
            upsert_rows=[self._row_from_doc(doc)],
            distance_metric="cosine_distance",
            schema=_ltm_schema(),
        )

    def update(self, memory_id: str, user_id: str, fields: Dict[str, Any]) -> None:
        current = self._fetch_one_by_filter(
            ["And", [["memory_id", "Eq", memory_id], ["user_id", "Eq", user_id]]]
        )
        if current is None:
            return
        merged = dict(current)
        merged.update(fields)
        merged["memory_id"] = memory_id
        merged["user_id"] = user_id
        merged["updated_at"] = _now_iso()
        self._client.write(
            self._namespace,
            upsert_rows=[self._row_from_doc(merged)],
            distance_metric="cosine_distance",
            schema=_ltm_schema(),
        )

    def get_by_id(
        self,
        memory_id: str,
        user_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        predicates: List[List[Any]] = [["memory_id", "Eq", memory_id]]
        if user_id is not None:
            predicates.append(["user_id", "Eq", user_id])
        if not include_deleted:
            predicates.append(["deleted", "Eq", 0])
        rec = self._fetch_one_by_filter(["And", predicates] if len(predicates) > 1 else predicates[0])
        if rec is None:
            return None
        return {"user_id": rec.get("user_id")}

    def get_many_by_ids(
        self, ids: List[str], user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        rows = self._fetch_many_by_ids(ids, user_id)
        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "memory_id": row.get("memory_id"),
                    "content": row.get("content", ""),
                    "summary": row.get("summary"),
                    "memory_category": row.get("memory_category", "semantic"),
                    "memory_subtype": row.get("memory_subtype", "domain"),
                    "entities": row.get("entities") or [],
                    "importance": float(row.get("importance", 0.5)),
                    "access_count": int(row.get("access_count", 0)),
                    "created_at": row.get("created_at"),
                    "metadata": row.get("metadata"),
                }
            )
        return out

    def count_for_user(self, user_id: str, include_deleted: bool = False) -> int:
        predicates: List[List[Any]] = [["user_id", "Eq", user_id]]
        if not include_deleted:
            predicates.append(["deleted", "Eq", 0])
        resp = self._client.query(
            self._namespace,
            rank_by=["id", "asc"],
            top_k=10000,
            filters=["And", predicates] if len(predicates) > 1 else predicates[0],
        )
        return len(resp.get("rows", []))

    def soft_delete(self, memory_id: str, user_id: str) -> None:
        self.update(
            memory_id,
            user_id,
            {"deleted": 1, "deleted_at": _now_iso()},
        )

    def hard_delete(self, memory_id: str, user_id: str) -> None:
        rec = self.get_by_id(memory_id, user_id=user_id, include_deleted=True)
        if rec is None:
            return
        self._client.write(self._namespace, deletes=[memory_id])

    def delete_all_for_user(self, user_id: str) -> None:
        resp = self._client.query(
            self._namespace,
            rank_by=["id", "asc"],
            top_k=10000,
            filters=["user_id", "Eq", user_id],
            include_attributes=["memory_id"],
        )
        ids = []
        for row in resp.get("rows", []):
            attrs = row.get("attributes") if isinstance(row, dict) else None
            if not isinstance(attrs, dict):
                attrs = dict(row)
            ids.append(str(attrs.get("memory_id") or row.get("id")))
        if ids:
            self._client.write(self._namespace, deletes=ids)

    def count_total(self, include_deleted: bool = False) -> int:
        filters = None if include_deleted else ["deleted", "Eq", 0]
        resp = self._client.query(
            self._namespace,
            rank_by=["id", "asc"],
            top_k=10000,
            filters=filters,
        )
        return len(resp.get("rows", []))

    def increment_access_count(self, memory_id: str) -> None:
        rec = self._fetch_one_by_filter(["memory_id", "Eq", memory_id])
        if rec is None:
            return
        current = int(rec.get("access_count", 0))
        rec["access_count"] = current + 1
        rec["last_accessed"] = _now_iso()
        self._client.write(
            self._namespace,
            upsert_rows=[self._row_from_doc(rec)],
            distance_metric="cosine_distance",
            schema=_ltm_schema(),
        )

    def get_category_counts(self) -> Dict[str, int]:
        resp = self._client.query(
            self._namespace,
            rank_by=["id", "asc"],
            top_k=10000,
            filters=["deleted", "Eq", 0],
            include_attributes=["memory_category"],
        )
        counts: Dict[str, int] = {}
        for row in resp.get("rows", []):
            attrs = row.get("attributes") if isinstance(row, dict) else None
            if not isinstance(attrs, dict):
                attrs = dict(row)
            category = attrs.get("memory_category") or "semantic"
            counts[category] = counts.get(category, 0) + 1
        return counts

    def get_top_accessed(self, limit: int = 5) -> List[Dict[str, Any]]:
        resp = self._client.query(
            self._namespace,
            rank_by=["id", "asc"],
            top_k=10000,
            filters=["deleted", "Eq", 0],
            include_attributes=[
                "memory_id",
                "memory_category",
                "access_count",
                "importance",
                "content",
            ],
        )
        rows = []
        for row in resp.get("rows", []):
            attrs = row.get("attributes") if isinstance(row, dict) else None
            if not isinstance(attrs, dict):
                attrs = dict(row)
            rows.append(
                {
                    "memory_id": str(attrs.get("memory_id") or row.get("id")),
                    "memory_category": attrs.get("memory_category", "semantic"),
                    "access_count": int(attrs.get("access_count", 0)),
                    "importance": float(attrs.get("importance", 0.5)),
                    "content": attrs.get("content", ""),
                }
            )
        rows.sort(key=lambda item: item["access_count"], reverse=True)
        return rows[: int(limit)]

    def get_storage_bytes(self) -> int:
        """Approximate logical bytes across Turbopuffer namespaces used by LAML."""
        namespaces = [
            config.turbopuffer.long_term_namespace,
            config.turbopuffer.sessions_namespace,
            config.turbopuffer.working_memory_namespace,
        ]
        total = 0
        for namespace in namespaces:
            try:
                meta = self._client.metadata(namespace)
                total += int(
                    meta.get("approx_logical_bytes")
                    or meta.get("approx_size_bytes")
                    or 0
                )
            except Exception:
                # Namespace might not exist yet; ignore.
                continue
        if total > 0:
            return total

        # Fallback for accounts/regions where metadata bytes are not surfaced yet.
        # Estimate by summing serialized row payload sizes.
        probes = [
            (
                config.turbopuffer.long_term_namespace,
                [
                    "vector",
                    "memory_id",
                    "content",
                    "summary",
                    "entities",
                    "metadata",
                    "importance",
                    "memory_category",
                ],
            ),
            (
                config.turbopuffer.sessions_namespace,
                ["session_id", "user_id", "context_data", "context_summary"],
            ),
            (
                config.turbopuffer.working_memory_namespace,
                ["item_id", "content", "content_type", "token_count", "session_id", "user_id"],
            ),
        ]
        estimated = 0
        for namespace, attrs in probes:
            try:
                resp = self._client.query(
                    namespace,
                    rank_by=["id", "asc"],
                    top_k=10000,
                    include_attributes=attrs,
                )
                for row in resp.get("rows", []):
                    estimated += len(json.dumps(row, ensure_ascii=True))
            except Exception:
                continue
        return estimated
        return total
