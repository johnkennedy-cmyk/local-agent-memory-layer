"""ClickHouse-backed repository for long-term memory (when vector backend=clickhouse)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config import config


def _get_ch_client():
    import clickhouse_connect

    ch = config.clickhouse
    return clickhouse_connect.get_client(
        host=ch.host,
        port=ch.port,
        database=ch.database,
        username=ch.user,
        password=ch.password or None,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class ClickHouseMemoryRepository:
    """
    Long-term memory CRUD against a ClickHouse table.

    Same table as ClickHouseVectorStore; schema created by init_clickhouse.py.
    """

    def __init__(self):
        self._client = _get_ch_client()
        self._table = config.clickhouse.table_name
        self._db = config.clickhouse.database

    def _full_table(self):
        return f"{self._db}.{self._table}"

    def insert(self, doc: Dict[str, Any]) -> None:
        """Insert one long-term memory row."""
        data = [
            [
                doc["memory_id"],
                doc["user_id"],
                doc.get("memory_category", "semantic"),
                doc.get("memory_subtype", "domain"),
                doc["content"],
                doc.get("summary") or "",
                list(doc["embedding"]),
                doc.get("entities") or [],
                doc.get("metadata") or "",
                doc.get("event_time") or None,
                1 if doc.get("is_temporal") else 0,
                float(doc.get("importance", 0.5)),
                0,
                doc.get("source_session") or "",
                doc.get("source_type") or "conversation",
                _now_iso(),
                _now_iso(),
                _now_iso(),
                None,
            ]
        ]
        self._client.insert(
            self._full_table(),
            data,
            column_names=[
                "memory_id", "user_id", "memory_category", "memory_subtype",
                "content", "summary", "embedding", "entities", "metadata",
                "event_time", "is_temporal", "importance", "access_count",
                "source_session", "source_type", "created_at", "last_accessed", "updated_at", "deleted_at",
            ],
        )

    def update(self, memory_id: str, user_id: str, fields: Dict[str, Any]) -> None:
        """Partial update via ALTER TABLE UPDATE."""
        if not fields:
            return
        set_parts = []
        params = {}
        for i, (k, v) in enumerate(fields.items()):
            if k == "updated_at":
                continue
            key = f"f{i}"
            params[key] = v
            if k == "embedding":
                set_parts.append(f"embedding = {{{key}:Array(Float32)}}")
            elif k == "entities":
                set_parts.append(f"entities = {{{key}:Array(String)}}")
            elif k in ("importance",):
                set_parts.append(f"{k} = {{{key}:Float32}}")
            else:
                set_parts.append(f"{k} = {{{key}:String}}")
        set_parts.append("updated_at = now()")
        params["mid"] = memory_id
        params["uid"] = user_id
        self._client.command(
            f"ALTER TABLE {self._full_table()} UPDATE {', '.join(set_parts)} WHERE memory_id = {{mid:String}} AND user_id = {{uid:String}}",
            parameters=params,
        )

    def get_by_id(
        self,
        memory_id: str,
        user_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Return one row as dict or None."""
        q = f"SELECT user_id FROM {self._full_table()} WHERE memory_id = {{mid:String}}"
        params = {"mid": memory_id}
        if not include_deleted:
            q += " AND deleted_at IS NULL"
        if user_id is not None:
            q += " AND user_id = {uid:String}"
            params["uid"] = user_id
        q += " LIMIT 1"
        result = self._client.query(q, parameters=params)
        rows = result.result_rows
        if not rows:
            return None
        return {"user_id": rows[0][0]}

    def get_many_by_ids(
        self, ids: List[str], user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return rows for given ids; exclude soft-deleted."""
        if not ids:
            return []
        # ClickHouse IN clause with parameters - use tuple or multiple OR
        placeholders = ",".join([f"{{id{i}:String}}" for i in range(len(ids))])
        params = {f"id{i}": id_ for i, id_ in enumerate(ids)}
        q = f"""
            SELECT memory_id, content, summary, memory_category, memory_subtype,
                   entities, importance, access_count, created_at, metadata
            FROM {self._full_table()}
            WHERE memory_id IN ({placeholders}) AND deleted_at IS NULL
        """
        if user_id is not None:
            q = q.replace("AND deleted_at", "AND user_id = {uid:String} AND deleted_at")
            params["uid"] = user_id
        result = self._client.query(q, parameters=params)
        return [
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
            for row in result.result_rows
        ]

    def count_for_user(self, user_id: str, include_deleted: bool = False) -> int:
        q = f"SELECT count() FROM {self._full_table()} WHERE user_id = {{uid:String}}"
        if not include_deleted:
            q += " AND deleted_at IS NULL"
        result = self._client.query(q, parameters={"uid": user_id})
        return int(result.result_rows[0][0]) if result.result_rows else 0

    def soft_delete(self, memory_id: str, user_id: str) -> None:
        self._client.command(
            f"ALTER TABLE {self._full_table()} UPDATE deleted_at = now() WHERE memory_id = {{mid:String}} AND user_id = {{uid:String}}",
            parameters={"mid": memory_id, "uid": user_id},
        )

    def hard_delete(self, memory_id: str, user_id: str) -> None:
        self._client.command(
            f"ALTER TABLE {self._full_table()} DELETE WHERE memory_id = {{mid:String}} AND user_id = {{uid:String}}",
            parameters={"mid": memory_id, "uid": user_id},
        )

    def delete_all_for_user(self, user_id: str) -> None:
        self._client.command(
            f"ALTER TABLE {self._full_table()} DELETE WHERE user_id = {{uid:String}}",
            parameters={"uid": user_id},
        )

    def count_total(self, include_deleted: bool = False) -> int:
        q = f"SELECT count() FROM {self._full_table()}"
        if not include_deleted:
            q += " WHERE deleted_at IS NULL"
        result = self._client.query(q)
        return int(result.result_rows[0][0]) if result.result_rows else 0

    def increment_access_count(self, memory_id: str) -> None:
        self._client.command(
            f"ALTER TABLE {self._full_table()} UPDATE access_count = access_count + 1, last_accessed = now() WHERE memory_id = {{mid:String}}",
            parameters={"mid": memory_id},
        )
