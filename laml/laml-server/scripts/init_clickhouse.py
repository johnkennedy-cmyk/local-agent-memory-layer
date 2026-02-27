#!/usr/bin/env python3
"""Create LAML database and long_term_memories table in ClickHouse."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config


def main():
    if config.vector_backend != "clickhouse":
        print("LAML_VECTOR_BACKEND is not 'clickhouse'; skipping.")
        return 0

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
