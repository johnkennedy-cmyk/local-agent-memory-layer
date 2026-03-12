#!/usr/bin/env python3
"""
One-time migration: copy long_term_memories from Firebolt into ClickHouse.

Reads all rows from the Firebolt long_term_memories table and inserts them into
the configured ClickHouse table using the same logical fields and embeddings.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Tuple

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import db  # Firebolt client
from src.config import config


def fetch_all_memories(batch_size: int = 1000) -> Iterable[List[Tuple[Any, ...]]]:
    """
    Generator that yields batches of rows from long_term_memories.
    """
    columns = [
        "memory_id",
        "user_id",
        "org_id",
        "memory_category",
        "memory_subtype",
        "content",
        "summary",
        "embedding",
        "entities",
        "metadata",
        "event_time",
        "is_temporal",
        "importance",
        "access_count",
        "decay_factor",
        "supersedes",
        "source_session",
        "source_type",
        "confidence",
        "created_at",
        "last_accessed",
        "updated_at",
        "deleted_at",
    ]

    count_rows = db.execute("SELECT COUNT(*) FROM long_term_memories", ())
    total = int(count_rows[0][0]) if count_rows else 0
    if total == 0:
        print("No rows found in long_term_memories; nothing to migrate.")
        return

    print(f"Found {total} rows in long_term_memories. Migrating in batches of {batch_size}...")
    pages = int(math.ceil(total / float(batch_size)))
    for page in range(pages):
        offset = page * batch_size
        query = f"""
            SELECT
                {", ".join(columns)}
            FROM long_term_memories
            ORDER BY created_at
            LIMIT {batch_size}
            OFFSET {offset}
        """
        rows = db.execute(query, ())
        if not rows:
            break
        yield rows


def row_to_clickhouse(row: Tuple[Any, ...]) -> Dict[str, Any]:
    """
    Convert a Firebolt row into a dict ready for ClickHouse insert.
    """
    (
        memory_id,
        user_id,
        org_id,
        memory_category,
        memory_subtype,
        content,
        summary,
        embedding,
        entities,
        metadata,
        event_time,
        is_temporal,
        importance,
        access_count,
        decay_factor,
        supersedes,
        source_session,
        source_type,
        confidence,
        created_at,
        last_accessed,
        updated_at,
        deleted_at,
    ) = row

    # Embedding: Firebolt ARRAY(REAL) often comes back as string "{0.1,0.2,...}"
    emb_list: List[float] = []
    if embedding is not None:
        try:
            if isinstance(embedding, str):
                cleaned = embedding.strip()
                if cleaned.startswith("{") and cleaned.endswith("}"):
                    cleaned = cleaned[1:-1]
                if cleaned:
                    emb_list = [float(x) for x in cleaned.split(",")]
            else:
                emb_list = [float(x) for x in embedding]
        except Exception:
            emb_list = []

    # Entities: Firebolt ARRAY(TEXT) -> list[str]
    entities_list: List[str] = []
    if entities:
        try:
            entities_list = [str(x) for x in entities]
        except Exception:
            entities_list = []

    return {
        "memory_id": memory_id,
        "user_id": user_id,
        "memory_category": memory_category,
        "memory_subtype": memory_subtype,
        "content": content,
        "summary": summary or "",
        "embedding": emb_list,
        "entities": entities_list,
        "metadata": metadata or "",
        "event_time": event_time,
        "is_temporal": bool(is_temporal) if is_temporal is not None else (event_time is not None),
        "importance": float(importance) if importance is not None else 0.5,
        "source_session": source_session or "",
        "source_type": source_type or "conversation",
        "deleted_at": deleted_at,
    }


def bulk_insert_clickhouse(docs: List[Dict[str, Any]]) -> None:
    """
    Insert a batch of documents into ClickHouse laml.long_term_memories.
    """
    if not docs:
        return

    import clickhouse_connect

    ch = config.clickhouse
    client = clickhouse_connect.get_client(
        host=ch.host,
        port=ch.port,
        database=ch.database,
        username=ch.user,
        password=ch.password or None,
    )

    table = f"{ch.database}.{ch.table_name}"

    data: List[List[Any]] = []
    for doc in docs:
        # Skip rows without memory_id or embedding
        if not doc.get("memory_id"):
            continue
        if not doc.get("embedding"):
            continue
        data.append(
            [
                doc["memory_id"],
                doc["user_id"],
                doc["memory_category"],
                doc["memory_subtype"],
                doc["content"],
                doc["summary"],
                list(doc["embedding"]),
                doc.get("entities") or [],
                doc.get("metadata") or "",
                doc.get("event_time"),
                1 if doc.get("is_temporal") else 0,
                float(doc.get("importance", 0.5)),
                0,  # access_count starts at 0
                doc.get("source_session") or "",
                doc.get("source_type") or "conversation",
                doc.get("deleted_at"),
            ]
        )

    if not data:
        return

    client.insert(
        table,
        data,
        column_names=[
            "memory_id",
            "user_id",
            "memory_category",
            "memory_subtype",
            "content",
            "summary",
            "embedding",
            "entities",
            "metadata",
            "event_time",
            "is_temporal",
            "importance",
            "access_count",
            "source_session",
            "source_type",
            "deleted_at",
        ],
    )
    print(f"Inserted {len(data)} rows into {table}")


def main() -> int:
    print("LAML - Firebolt → ClickHouse long_term_memories migration")
    total = 0
    for rows in fetch_all_memories():
        docs = [row_to_clickhouse(row) for row in rows]
        bulk_insert_clickhouse(docs)
        total += len(docs)
        print(f"Total processed so far: {total}")
    print(f"Migration completed. Total rows processed from Firebolt: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

