#!/usr/bin/env python3
"""Create LAML database and tables in ClickHouse (long_term_memories, session_contexts, working_memory_items)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config


def main():
    import clickhouse_connect

    ch = config.clickhouse
    client = clickhouse_connect.get_client(
        host=ch.host,
        port=ch.port,
        database="default",
        username=ch.user,
        password=ch.password or None,
    )

    client.command(f"CREATE DATABASE IF NOT EXISTS {ch.database}")
    client.database = ch.database
    dim = ch.embedding_dimensions
    table = ch.table_name
    full = f"{ch.database}.{table}"

    # Long-term memories (vector store)
    client.command(f"""
        CREATE TABLE IF NOT EXISTS {full} (
            memory_id String,
            user_id String,
            memory_category String,
            memory_subtype String,
            content String,
            summary String,
            embedding Array(Float32),
            entities Array(String),
            metadata String,
            event_time Nullable(DateTime64(3)),
            is_temporal UInt8 DEFAULT 0,
            importance Float32 DEFAULT 0.5,
            access_count UInt32 DEFAULT 0,
            source_session String DEFAULT '',
            source_type String DEFAULT 'conversation',
            created_at DateTime64(3) DEFAULT now64(3),
            last_accessed DateTime64(3) DEFAULT now64(3),
            updated_at DateTime64(3) DEFAULT now64(3),
            deleted_at Nullable(DateTime64(3))
        ) ENGINE = MergeTree()
        ORDER BY (user_id, memory_id)
    """)
    print(f"Created table {full} with embedding dimension {dim}.")

    # Session contexts (unified backend)
    sessions_table = ch.sessions_table
    sessions_full = f"{ch.database}.{sessions_table}"
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
    print(f"Created table {sessions_full}.")

    # Working memory items (unified backend)
    wm_table = ch.working_memory_table
    wm_full = f"{ch.database}.{wm_table}"
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
    print(f"Created table {wm_full}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
