"""DuckDB-backed repository for long-term memory (when vector backend=duckdb)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import os

import duckdb  # type: ignore[import]

from src.config import config


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class DuckDBMemoryRepository:
    """
    Long-term memory CRUD against a DuckDB table.

    This is intended for local development and small-scale testing, not
    production-scale vector search.
    """

    def __init__(self) -> None:
        self._path = config.duckdb.path
        self._table = config.duckdb.table_name
        # Create database directory if needed
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        self._conn = duckdb.connect(self._path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
                memory_id TEXT PRIMARY KEY,
                user_id TEXT,
                memory_category TEXT,
                memory_subtype TEXT,
                content TEXT,
                summary TEXT,
                embedding FLOAT[],
                entities TEXT[],
                importance DOUBLE,
                event_time TIMESTAMP,
                metadata TEXT,
                is_temporal BOOLEAN,
                source_session TEXT,
                source_type TEXT,
                access_count BIGINT,
                created_at TIMESTAMP,
                last_accessed TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP
            )
            """
        )

    # Basic CRUD mirrors FireboltMemoryRepository, but using DuckDB SQL.

    def insert(self, doc: Dict[str, Any]) -> None:
        now = _now_iso()
        self._conn.execute(
            f"""
            INSERT OR REPLACE INTO {self._table} (
                memory_id, user_id, memory_category, memory_subtype,
                content, summary, embedding, entities, importance,
                event_time, metadata, is_temporal, source_session,
                source_type, access_count, created_at, last_accessed,
                updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                doc["memory_id"],
                doc["user_id"],
                doc.get("memory_category", "semantic"),
                doc.get("memory_subtype", "domain"),
                doc["content"],
                doc.get("summary"),
                list(doc.get("embedding") or []),
                list(doc.get("entities") or []),
                float(doc.get("importance", 0.5)),
                doc.get("event_time"),
                doc.get("metadata"),
                bool(doc.get("is_temporal", False)),
                doc.get("source_session") or "",
                doc.get("source_type", "conversation"),
                0,
                now,
                now,
                now,
                None,
            ],
        )

    def update(self, memory_id: str, user_id: str, fields: Dict[str, Any]) -> None:
        if not fields:
            return
        sets = []
        params: List[Any] = []
        for k, v in fields.items():
            if k in ("updated_at",):
                continue
            sets.append(f"{k} = ?")
            if k == "embedding":
                params.append(list(v))
            else:
                params.append(v)
        if not sets:
            return
        sets.append("updated_at = ?")
        params.append(_now_iso())
        params.extend([memory_id, user_id])
        self._conn.execute(
            f"""
            UPDATE {self._table}
            SET {", ".join(sets)}
            WHERE memory_id = ? AND user_id = ?
            """,
            params,
        )

    def get_by_id(
        self,
        memory_id: str,
        user_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        q = f"SELECT user_id, deleted_at FROM {self._table} WHERE memory_id = ?"
        params: List[Any] = [memory_id]
        rows = self._conn.execute(q, params).fetchall()
        if not rows:
            return None
        uid, deleted_at = rows[0]
        if not include_deleted and deleted_at is not None:
            return None
        if user_id is not None and uid != user_id:
            return None
        return {"user_id": uid}

    def get_many_by_ids(
        self, ids: List[str], user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join(["?"] * len(ids))
        base = f"""
            SELECT memory_id, content, summary, memory_category, memory_subtype,
                   entities, importance, access_count, created_at, metadata
            FROM {self._table}
            WHERE memory_id IN ({placeholders}) AND deleted_at IS NULL
        """
        params: List[Any] = list(ids)
        if user_id is not None:
            base += " AND user_id = ?"
            params.append(user_id)
        rows = self._conn.execute(base, params).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "memory_id": row[0],
                    "content": row[1],
                    "summary": row[2],
                    "memory_category": row[3],
                    "memory_subtype": row[4],
                    "entities": row[5] or [],
                    "importance": row[6],
                    "access_count": row[7],
                    "created_at": row[8],
                    "metadata": row[9],
                }
            )
        return result

    def count_for_user(self, user_id: str, include_deleted: bool = False) -> int:
        q = f"SELECT COUNT(*) FROM {self._table} WHERE user_id = ?"
        params: List[Any] = [user_id]
        if not include_deleted:
            q += " AND deleted_at IS NULL"
        rows = self._conn.execute(q, params).fetchall()
        return int(rows[0][0]) if rows else 0

    def soft_delete(self, memory_id: str, user_id: str) -> None:
        self._conn.execute(
            f"""
            UPDATE {self._table}
            SET deleted_at = ?, updated_at = ?
            WHERE memory_id = ? AND user_id = ?
            """,
            [_now_iso(), _now_iso(), memory_id, user_id],
        )

    def hard_delete(self, memory_id: str, user_id: str) -> None:
        self._conn.execute(
            f"DELETE FROM {self._table} WHERE memory_id = ? AND user_id = ?",
            [memory_id, user_id],
        )

    def delete_all_for_user(self, user_id: str) -> None:
        self._conn.execute(
            f"DELETE FROM {self._table} WHERE user_id = ?",
            [user_id],
        )

    def count_total(self, include_deleted: bool = False) -> int:
        q = f"SELECT COUNT(*) FROM {self._table}"
        if not include_deleted:
            q += " WHERE deleted_at IS NULL"
        rows = self._conn.execute(q).fetchall()
        return int(rows[0][0]) if rows else 0

    def increment_access_count(self, memory_id: str) -> None:
        self._conn.execute(
            f"""
            UPDATE {self._table}
            SET access_count = COALESCE(access_count, 0) + 1,
                last_accessed = ?
            WHERE memory_id = ?
            """,
            [_now_iso(), memory_id],
        )

    def get_category_counts(self) -> Dict[str, int]:
        rows = self._conn.execute(
            f"""
            SELECT memory_category, COUNT(*) as cnt
            FROM {self._table}
            WHERE deleted_at IS NULL
            GROUP BY memory_category
            """
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def get_top_accessed(self, limit: int = 5) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            f"""
            SELECT memory_id, memory_category, access_count, importance, content
            FROM {self._table}
            WHERE deleted_at IS NULL
            ORDER BY access_count DESC, importance DESC
            LIMIT {int(limit)}
            """
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "memory_id": row[0],
                    "memory_category": row[1],
                    "access_count": row[2],
                    "importance": row[3],
                    "content": row[4] or "",
                }
            )
        return out

    def get_storage_bytes(self) -> int:
        """Return approximate file size of the DuckDB database."""
        try:
            return os.path.getsize(self._path)
        except OSError:
            return 0
