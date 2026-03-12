"""ClickHouse-backed working memory store (when vector backend=clickhouse)."""

from __future__ import annotations

from typing import List, Optional, Tuple

from src.config import config
from src.db.working_memory_store import WorkingMemoryStore, WorkingMemoryItem


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


class WorkingMemoryStoreClickHouse(WorkingMemoryStore):
    """ClickHouse-backed working memory store using working_memory_items table."""

    def __init__(self):
        self._client = _get_ch_client()
        self._table = config.clickhouse.working_memory_table
        self._db = config.clickhouse.database

    def _full_table(self) -> str:
        return f"{self._db}.{self._table}"

    def get_next_sequence_num(self, session_id: str) -> int:
        result = self._client.query(
            f"SELECT coalesce(max(sequence_num), 0) + 1 FROM {self._full_table()} WHERE session_id = {{sid:String}}",
            parameters={"sid": session_id},
        )
        return int(result.result_rows[0][0]) if result.result_rows else 1

    def insert_item(self, item: WorkingMemoryItem) -> None:
        self._client.insert(
            self._full_table(),
            [[
                item.item_id,
                item.session_id,
                item.user_id,
                item.content_type,
                item.content,
                item.token_count,
                item.relevance_score,
                1 if item.pinned else 0,
                item.sequence_num,
            ]],
            column_names=[
                "item_id", "session_id", "user_id", "content_type", "content",
                "token_count", "relevance_score", "pinned", "sequence_num",
            ],
        )

    def get_items_for_session(
        self,
        session_id: str,
        include_types: Optional[List[str]] = None,
    ) -> List[WorkingMemoryItem]:
        q = f"""
            SELECT item_id, session_id, user_id, content_type, content,
                   token_count, pinned, relevance_score, sequence_num
            FROM {self._full_table()}
            WHERE session_id = {{sid:String}}
        """
        params: dict = {"sid": session_id}
        if include_types:
            placeholders = ",".join([f"{{t{i}:String}}" for i in range(len(include_types))])
            q += f" AND content_type IN ({placeholders})"
            for i, t in enumerate(include_types):
                params[f"t{i}"] = t
        q += " ORDER BY pinned DESC, relevance_score DESC, sequence_num DESC"
        result = self._client.query(q, parameters=params)
        return [
            WorkingMemoryItem(
                item_id=row[0],
                session_id=row[1],
                user_id=row[2],
                content_type=row[3],
                content=row[4],
                token_count=int(row[5]),
                pinned=bool(row[6]),
                relevance_score=float(row[7]),
                sequence_num=int(row[8]),
            )
            for row in result.result_rows
        ]

    def count_items(
        self,
        session_id: str,
        pinned_only: Optional[bool] = None,
    ) -> int:
        q = f"SELECT count() FROM {self._full_table()} WHERE session_id = {{sid:String}}"
        params: dict = {"sid": session_id}
        if pinned_only is not None:
            q += " AND pinned = {pinned:UInt8}"
            params["pinned"] = 1 if pinned_only else 0
        result = self._client.query(q, parameters=params)
        return int(result.result_rows[0][0]) if result.result_rows else 0

    def delete_items(
        self,
        session_id: str,
        pinned_only: Optional[bool] = None,
    ) -> None:
        q = f"ALTER TABLE {self._full_table()} DELETE WHERE session_id = {{sid:String}}"
        params: dict = {"sid": session_id}
        if pinned_only is not None:
            q += " AND pinned = {pinned:UInt8}"
            params["pinned"] = 1 if pinned_only else 0
        self._client.command(q, parameters=params)

    def sum_tokens(self, session_id: str) -> int:
        result = self._client.query(
            f"SELECT coalesce(sum(token_count), 0) FROM {self._full_table()} WHERE session_id = {{sid:String}}",
            parameters={"sid": session_id},
        )
        return int(result.result_rows[0][0]) if result.result_rows else 0

    def count_all(self) -> int:
        result = self._client.query(f"SELECT count() FROM {self._full_table()}")
        return int(result.result_rows[0][0]) if result.result_rows else 0

    def sum_tokens_all(self) -> int:
        result = self._client.query(
            f"SELECT coalesce(sum(token_count), 0) FROM {self._full_table()}"
        )
        return int(result.result_rows[0][0]) if result.result_rows else 0

    def update_item_flags(
        self,
        item_id: str,
        session_id: str,
        pinned: Optional[bool],
        relevance_score: Optional[float],
    ) -> None:
        updates = []
        params: dict = {"iid": item_id, "sid": session_id}
        if pinned is not None:
            updates.append("pinned = {pinned:UInt8}")
            params["pinned"] = 1 if pinned else 0
        if relevance_score is not None:
            updates.append("relevance_score = {score:Float32}")
            params["score"] = relevance_score
        if not updates:
            return
        updates.append("last_accessed = now()")
        self._client.command(
            f"ALTER TABLE {self._full_table()} UPDATE {', '.join(updates)} WHERE item_id = {{iid:String}} AND session_id = {{sid:String}}",
            parameters=params,
        )

    def eviction_candidates(self, session_id: str) -> List[Tuple[str, int, float]]:
        result = self._client.query(
            f"""
            SELECT item_id, token_count, relevance_score
            FROM {self._full_table()}
            WHERE session_id = {{sid:String}} AND pinned = 0
            ORDER BY relevance_score ASC, sequence_num ASC
            """,
            parameters={"sid": session_id},
        )
        return [
            (row[0], int(row[1]), float(row[2]))
            for row in result.result_rows
        ]

    def delete_item(self, item_id: str) -> None:
        self._client.command(
            f"ALTER TABLE {self._full_table()} DELETE WHERE item_id = {{iid:String}}",
            parameters={"iid": item_id},
        )
