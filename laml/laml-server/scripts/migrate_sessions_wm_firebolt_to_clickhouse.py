#!/usr/bin/env python3
"""
One-time migration: copy session_contexts and working_memory_items from Firebolt to ClickHouse.

Run with Firebolt as source and CLICKHOUSE_* set. Ensures database and tables exist, then inserts.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import db
from src.config import config


def _get_ch_client():
    import clickhouse_connect
    ch = config.clickhouse
    return clickhouse_connect.get_client(
        host=ch.host,
        port=ch.port,
        database="default",
        username=ch.user,
        password=ch.password or None,
    )


def ensure_tables(client):
    """Create database and session_contexts / working_memory_items tables if not exist."""
    ch = config.clickhouse
    client.command(f"CREATE DATABASE IF NOT EXISTS {ch.database}")
    client.database = ch.database

    sessions_full = f"{ch.database}.{ch.sessions_table}"
    client.command(f"""
        CREATE TABLE IF NOT EXISTS {sessions_full} (
            session_id String,
            user_id String,
            org_id String DEFAULT '',
            total_tokens Int32 DEFAULT 0,
            max_tokens Int32 DEFAULT 8000,
            created_at DateTime64(3) DEFAULT now64(3),
            last_activity DateTime64(3) DEFAULT now64(3)
        ) ENGINE = MergeTree()
        ORDER BY session_id
    """)

    wm_full = f"{ch.database}.{ch.working_memory_table}"
    client.command(f"""
        CREATE TABLE IF NOT EXISTS {wm_full} (
            item_id String,
            session_id String,
            user_id String,
            content_type String,
            content String,
            token_count Int32 NOT NULL,
            relevance_score Float32 DEFAULT 1.0,
            pinned UInt8 DEFAULT 0,
            sequence_num Int32 NOT NULL,
            created_at DateTime64(3) DEFAULT now64(3),
            last_accessed DateTime64(3) DEFAULT now64(3)
        ) ENGINE = MergeTree()
        ORDER BY (session_id, item_id)
    """)
    print(f"Ensured tables {sessions_full}, {wm_full}")


def migrate_sessions(client) -> int:
    """Copy session_contexts from Firebolt to ClickHouse."""
    rows = db.execute("""
        SELECT session_id, user_id, org_id, total_tokens, max_tokens
        FROM session_contexts
        ORDER BY session_id
    """)
    if not rows:
        print("No session_contexts rows in Firebolt.")
        return 0

    ch = config.clickhouse
    table = f"{ch.database}.{ch.sessions_table}"
    data = [[row[0], row[1], row[2] or "", int(row[3] or 0), int(row[4] or 8000)] for row in rows]
    client.insert(table, data, column_names=["session_id", "user_id", "org_id", "total_tokens", "max_tokens"])
    print(f"Migrated {len(data)} sessions to {table}")
    return len(data)


def migrate_working_memory(client) -> int:
    """Copy working_memory_items from Firebolt to ClickHouse."""
    rows = db.execute("""
        SELECT item_id, session_id, user_id, content_type, content, token_count,
               relevance_score, pinned, sequence_num
        FROM working_memory_items
        ORDER BY session_id, sequence_num
    """)
    if not rows:
        print("No working_memory_items rows in Firebolt.")
        return 0

    ch = config.clickhouse
    table = f"{ch.database}.{ch.working_memory_table}"
    data = [
        [row[0], row[1], row[2], row[3], row[4], int(row[5]), float(row[6]), 1 if row[7] else 0, int(row[8])]
        for row in rows
    ]
    client.insert(
        table,
        data,
        column_names=["item_id", "session_id", "user_id", "content_type", "content", "token_count", "relevance_score", "pinned", "sequence_num"],
    )
    print(f"Migrated {len(data)} working memory items to {table}")
    return len(data)


def main() -> int:
    print("LAML - Firebolt → ClickHouse (sessions + working memory)")
    if config.vector_backend != "clickhouse":
        print("Set LAML_VECTOR_BACKEND=clickhouse and CLICKHOUSE_* vars. Proceeding anyway.")
    client = _get_ch_client()
    ensure_tables(client)
    n_sessions = migrate_sessions(client)
    n_wm = migrate_working_memory(client)
    print(f"Done. Sessions: {n_sessions}, Working memory items: {n_wm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
