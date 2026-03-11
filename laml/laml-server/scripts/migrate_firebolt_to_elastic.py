#!/usr/bin/env python3
"""
One-time migration: copy long_term_memories from Firebolt into Elasticsearch.

Reads all rows from the Firebolt long_term_memories table and indexes them into
the configured Elasticsearch index using the same field names and embedding vectors.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Tuple

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import db  # Firebolt client
from src.config import config
from scripts.init_elastic_index import get_elasticsearch_client  # type: ignore


def fetch_all_memories(batch_size: int = 1000) -> Iterable[List[Tuple[Any, ...]]]:
    """
    Generator that yields batches of rows from long_term_memories.

    Uses OFFSET/LIMIT pagination which is acceptable for the expected dataset size.
    """
    # Column order must match schema.sql definition
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

    # Get total count to know how many pages we have
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


def row_to_doc(row: Tuple[Any, ...]) -> Dict[str, Any]:
    """
    Convert a Firebolt row tuple into an Elasticsearch document that matches
    the mapping in init_elastic_index.build_index_body.
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

    # Firebolt returns embedding as a JSON-like array; ensure it's a plain list[float]
    emb_list: List[float] = []
    if embedding is not None:
        try:
            # Firebolt Core returns ARRAY(REAL) as a string like "{0.1,0.2,...}"
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

    # Entities column is ARRAY(TEXT) in Firebolt; ensure list[str]
    entities_list: List[str] = []
    if entities:
        try:
            entities_list = [str(x) for x in entities]
        except Exception:
            entities_list = []

    # Elasticsearch expects ISO8601 or epoch_millis; Firebolt timestamps may come as strings
    def _to_iso(value: Any) -> Any:
        if value is None:
            return None
        # Datetime-like objects
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        # Strings from Firebolt typically look like "2026-02-27 13:42:09.012987"
        if isinstance(value, str):
            v = value.strip()
            # Replace space with 'T' so it matches strict_date_optional_time
            if " " in v and "T" not in v:
                v = v.replace(" ", "T", 1)
            return v
        return str(value)

    doc: Dict[str, Any] = {
        "memory_id": memory_id,
        "user_id": user_id,
        "org_id": org_id,
        "memory_category": memory_category,
        "memory_subtype": memory_subtype,
        "content": content,
        "summary": summary,
        "embedding": emb_list,
        "entities": entities_list,
        "metadata": metadata,
        "event_time": _to_iso(event_time),
        "is_temporal": is_temporal,
        "importance": importance,
        "access_count": access_count,
        "decay_factor": decay_factor,
        "supersedes": supersedes,
        "source_session": source_session,
        "source_type": source_type,
        "confidence": confidence,
        "created_at": _to_iso(created_at),
        "last_accessed": _to_iso(last_accessed),
        "updated_at": _to_iso(updated_at),
        "deleted_at": _to_iso(deleted_at),
    }
    return doc


def bulk_index(es_client, index_name: str, docs: List[Dict[str, Any]]) -> None:
    """
    Use Elasticsearch Bulk API to index a batch of documents.
    """
    if not docs:
        return

    actions: List[Dict[str, Any]] = []
    for doc in docs:
        # Skip docs with missing id
        if not doc.get("memory_id"):
            continue
        # Skip docs with empty or mismatched embeddings, since ES dense_vector requires fixed dims
        emb = doc.get("embedding") or []
        if not isinstance(emb, list) or len(emb) != config.elastic.embedding_dimensions:
            print(f"Skipping memory_id={doc.get('memory_id')} due to invalid embedding length={len(emb)}")
            continue
        actions.append(
            {
                "_op_type": "index",
                "_index": index_name,
                "_id": doc["memory_id"],
                "_source": doc,
            }
        )

    if not actions:
        return

    from elasticsearch import helpers  # imported here to avoid unused import when script is idle

    success, errors = helpers.bulk(es_client, actions, raise_on_error=False)
    print(f"Indexed batch: {success} successes, {len(errors)} errors")
    if errors:
        # Drop docs that failed due to mapping/parse issues (e.g., legacy timestamps) so we can proceed.
        print("Sample errors:", errors[:3])


def main() -> int:
    if not config.firebolt.use_core:
        print("Warning: FIREBOLT_USE_CORE=false. This script is intended for Firebolt Core migrations.")
    if config.vector_backend != "elastic":
        print("Warning: LAML_VECTOR_BACKEND is not 'elastic'. Elasticsearch index should still be created first.")

    es_client = get_elasticsearch_client()
    index_name = config.elastic.index_name

    total_indexed = 0
    for rows in fetch_all_memories():
        docs = [row_to_doc(row) for row in rows]
        bulk_index(es_client, index_name, docs)
        total_indexed += len(docs)
        print(f"Total indexed so far: {total_indexed}")

    print(f"Migration completed. Total documents attempted: {total_indexed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

