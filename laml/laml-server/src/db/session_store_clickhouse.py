"""ClickHouse-backed session store (when vector backend=clickhouse)."""

from __future__ import annotations

from src.config import config
from src.db.session_store import SessionStore, SessionRecord


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


class SessionStoreClickHouse(SessionStore):
    """ClickHouse-backed session store using session_contexts table."""

    def __init__(self):
        self._client = _get_ch_client()
        self._table = config.clickhouse.sessions_table
        self._db = config.clickhouse.database

    def _full_table(self) -> str:
        return f"{self._db}.{self._table}"

    def get_session(self, session_id: str) -> SessionRecord | None:
        q = f"""
            SELECT session_id, user_id, org_id, total_tokens, max_tokens
            FROM {self._full_table()}
            WHERE session_id = {{sid:String}}
            LIMIT 1
        """
        result = self._client.query(q, parameters={"sid": session_id})
        rows = result.result_rows
        if not rows:
            return None
        row = rows[0]
        return SessionRecord(
            session_id=row[0],
            user_id=row[1],
            org_id=row[2],
            total_tokens=int(row[3] or 0),
            max_tokens=int(row[4] or 8000),
        )

    def create_session(
        self,
        session_id: str,
        user_id: str,
        org_id: str | None,
        max_tokens: int,
    ) -> SessionRecord:
        self._client.insert(
            self._full_table(),
            [[session_id, user_id, org_id or "", 0, max_tokens]],
            column_names=["session_id", "user_id", "org_id", "total_tokens", "max_tokens"],
        )
        return SessionRecord(
            session_id=session_id,
            user_id=user_id,
            org_id=org_id,
            total_tokens=0,
            max_tokens=max_tokens,
        )

    def touch_session(self, session_id: str) -> None:
        self._client.command(
            f"ALTER TABLE {self._full_table()} UPDATE last_activity = now() WHERE session_id = {{sid:String}}",
            parameters={"sid": session_id},
        )

    def update_total_tokens(self, session_id: str, new_total: int) -> None:
        self._client.command(
            f"ALTER TABLE {self._full_table()} UPDATE total_tokens = {{total:Int32}} WHERE session_id = {{sid:String}}",
            parameters={"total": new_total, "sid": session_id},
        )

    def increment_total_tokens(self, session_id: str, delta: int) -> None:
        self._client.command(
            f"""
            ALTER TABLE {self._full_table()}
            UPDATE total_tokens = total_tokens + {{delta:Int32}}, last_activity = now()
            WHERE session_id = {{sid:String}}
            """,
            parameters={"delta": delta, "sid": session_id},
        )

    def count_all(self) -> int:
        result = self._client.query(f"SELECT count() FROM {self._full_table()}")
        return int(result.result_rows[0][0]) if result.result_rows else 0
