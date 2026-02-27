from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.db.client import db
from src.memory.vector_store import VectorSearchResult, VectorStore


class FireboltVectorStore(VectorStore):
    """
    VectorStore implementation backed by the existing Firebolt Core / Cloud schema.

    This is a thin adapter around the `long_term_memories` table and its HNSW index.
    """

    def upsert_embeddings(
        self,
        items: Sequence[Tuple[str, Sequence[float], Dict[str, Any]]],
    ) -> None:
        """
        Upsert embeddings into long_term_memories.

        For now this assumes the caller has already created or updated the row
        in `long_term_memories` and only needs the embedding column set.
        """
        for memory_id, embedding, _metadata in items:
            db.execute(
                """
                UPDATE long_term_memories
                SET embedding = ?
                WHERE memory_id = ?
                """,
                (list(embedding), memory_id),
            )

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """
        Perform a vector similarity search using the HNSW index on Firebolt Core.

        This mirrors the original Firebolt-specific SQL that used the `vector_search`
        TVF plus `VECTOR_COSINE_SIMILARITY`.
        """

        def _format_embedding_literal(values: Sequence[float]) -> str:
            # Firebolt expects a JSON-like numeric array literal, e.g. [0.1, 0.2, ...]
            return "[" + ", ".join(str(v) for v in values) + "]"

        embedding_literal = _format_embedding_literal(query_embedding)

        # Build optional filter on user_id
        user_filter_clause = ""
        params: List[Any] = []
        if filters and "user_id" in filters:
            user_filter_clause = "AND user_id = ?"
            params.append(filters["user_id"])

        # Fetch more candidates than needed so callers can post-filter if desired
        rows = db.execute(
            f"""
            SELECT
                memory_id,
                user_id,
                memory_category,
                memory_subtype,
                importance,
                created_at,
                VECTOR_COSINE_SIMILARITY(embedding, {embedding_literal}) AS similarity
            FROM vector_search(
                INDEX idx_memories_embedding,
                {embedding_literal},
                {top_k},
                64
            )
            WHERE deleted_at IS NULL
              {user_filter_clause}
            ORDER BY similarity DESC, importance DESC
            """,
            tuple(params),
        )

        results: List[VectorSearchResult] = []
        for row in rows:
            (
                memory_id,
                user_id,
                memory_category,
                memory_subtype,
                importance,
                created_at,
                similarity,
            ) = row
            results.append(
                VectorSearchResult(
                    memory_id=memory_id,
                    score=float(similarity),
                    metadata={
                        "user_id": user_id,
                        "memory_category": memory_category,
                        "memory_subtype": memory_subtype,
                        "importance": importance,
                        "created_at": created_at,
                    },
                )
            )

        return results

    def delete(self, ids: Sequence[str]) -> None:
        """Soft-delete memories by setting deleted_at."""
        for memory_id in ids:
            db.execute(
                """
                UPDATE long_term_memories
                SET deleted_at = CURRENT_TIMESTAMP()
                WHERE memory_id = ?
                """,
                (memory_id,),
            )
