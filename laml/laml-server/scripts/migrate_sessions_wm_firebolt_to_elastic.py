#!/usr/bin/env python3
"""
One-time migration: copy session_contexts and working_memory_items from Firebolt to Elasticsearch.

Run with Firebolt as source (FIREBOLT_USE_CORE=true or cloud) and ELASTICSEARCH_* set.
Creates laml_sessions and laml_working_memory indices if needed, then bulk indexes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import db
from src.config import config
from scripts.init_elastic_index import (
    get_elasticsearch_client,
    build_sessions_index_body,
    build_working_memory_index_body,
)


def _to_iso(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, str):
        v = value.strip()
        if " " in v and "T" not in v:
            v = v.replace(" ", "T", 1)
        return v
    return str(value)


def migrate_sessions(es_client) -> int:
    """Copy session_contexts from Firebolt to laml_sessions index."""
    index_name = config.elastic.sessions_index
    if not es_client.indices.exists(index=index_name):
        es_client.indices.create(index=index_name, body=build_sessions_index_body())
        print(f"Created index {index_name}")

    rows = db.execute("""
        SELECT session_id, user_id, org_id, total_tokens, max_tokens, created_at, last_activity
        FROM session_contexts
        ORDER BY session_id
    """)
    if not rows:
        print("No session_contexts rows in Firebolt.")
        return 0

    count = 0
    for row in rows:
        doc = {
            "session_id": row[0],
            "user_id": row[1],
            "org_id": row[2],
            "total_tokens": int(row[3] or 0),
            "max_tokens": int(row[4] or 8000),
            "created_at": _to_iso(row[5]),
            "last_activity": _to_iso(row[6]),
        }
        es_client.index(index=index_name, id=row[0], document=doc, refresh=True)
        count += 1
    print(f"Migrated {count} sessions to {index_name}")
    return count


def migrate_working_memory(es_client) -> int:
    """Copy working_memory_items from Firebolt to laml_working_memory index."""
    index_name = config.elastic.working_memory_index
    if not es_client.indices.exists(index=index_name):
        es_client.indices.create(index=index_name, body=build_working_memory_index_body())
        print(f"Created index {index_name}")

    rows = db.execute("""
        SELECT item_id, session_id, user_id, content_type, content, token_count,
               pinned, relevance_score, sequence_num, created_at, last_accessed
        FROM working_memory_items
        ORDER BY session_id, sequence_num
    """)
    if not rows:
        print("No working_memory_items rows in Firebolt.")
        return 0

    count = 0
    for row in rows:
        doc = {
            "item_id": row[0],
            "session_id": row[1],
            "user_id": row[2],
            "content_type": row[3],
            "content": row[4],
            "token_count": int(row[5]),
            "pinned": bool(row[6]),
            "relevance_score": float(row[7]),
            "sequence_num": int(row[8]),
            "created_at": _to_iso(row[9]),
            "last_accessed": _to_iso(row[10]),
        }
        es_client.index(index=index_name, id=row[0], document=doc, refresh=True)
        count += 1
    print(f"Migrated {count} working memory items to {index_name}")
    return count


def main() -> int:
    print("LAML - Firebolt → Elasticsearch (sessions + working memory)")
    if config.vector_backend != "elastic":
        print("Set LAML_VECTOR_BACKEND=elastic and ELASTICSEARCH_* vars. Proceeding anyway.")
    es_client = get_elasticsearch_client()
    n_sessions = migrate_sessions(es_client)
    n_wm = migrate_working_memory(es_client)
    print(f"Done. Sessions: {n_sessions}, Working memory items: {n_wm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
