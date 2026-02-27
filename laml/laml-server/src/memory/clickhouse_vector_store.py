"""ClickHouse-backed VectorStore implementation for LAML long-term memory."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.config import config
from src.memory.vector_store import VectorSearchResult, VectorStore


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


class ClickHouseVectorStore(VectorStore):
    """
    VectorStore implementation backed by ClickHouse.

    Uses cosineDistance for similarity search; same table as ClickHouseMemoryRepository.
    """

    def __init__(self):
        self._client = _get_ch_client()
        self._table = config.clickhouse.table_name
        self._db = config.clickhouse.database

    def _full_table(self):
        return f"{self._db}.{self._table}"

    def upsert_embeddings(
        self,
        items: Sequence[Tuple[str, Sequence[float], Dict[str, Any]]],
    ) -> None:
        """Update embedding for existing rows via ALTER TABLE UPDATE."""
        for memory_id, embedding, _ in items:
            emb_list = list(embedding)
            self._client.command(
                f"ALTER TABLE {self._full_table()} UPDATE embedding = {{emb:Array(Float32)}}, updated_at = now() WHERE memory_id = {{mid:String}}",
                parameters={"emb": emb_list, "mid": memory_id},
            )

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Vector search using cosineDistance (lower = more similar). Excludes soft-deleted."""
        # Build vector literal to avoid Array parameter binding issues
        vec_lit = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"
        q = f"""
            SELECT memory_id, user_id, memory_category, memory_subtype, importance, created_at,
                   cosineDistance(embedding, {vec_lit}) AS dist
            FROM {self._full_table()}
            WHERE deleted_at IS NULL
        """
        if filters and filters.get("user_id"):
            q += " AND user_id = {uid:String}"
        q += " ORDER BY dist ASC LIMIT {k:UInt32}"
        params = {"k": top_k}
        if filters and filters.get("user_id"):
            params["uid"] = filters["user_id"]
        result = self._client.query(q, parameters=params)
        results = []
        for row in result.result_rows:
            memory_id, user_id, cat, subtype, imp, created_at, dist = row
            # Convert distance to similarity: 1 - (dist/2) for cosine, clamped
            sim = max(0.0, min(1.0, 1.0 - (float(dist) / 2.0)))
            results.append(
                VectorSearchResult(
                    memory_id=memory_id,
                    score=sim,
                    metadata={
                        "user_id": user_id,
                        "memory_category": cat,
                        "memory_subtype": subtype,
                        "importance": imp,
                        "created_at": created_at,
                    },
                )
            )
        return results

    def delete(self, ids: Sequence[str]) -> None:
        """Soft-delete: set deleted_at."""
        for memory_id in ids:
            self._client.command(
                f"ALTER TABLE {self._full_table()} UPDATE deleted_at = now() WHERE memory_id = {{mid:String}}",
                parameters={"mid": memory_id},
            )
