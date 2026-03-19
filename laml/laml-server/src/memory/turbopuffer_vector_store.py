"""Turbopuffer-backed VectorStore implementation for LAML long-term memory."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.config import config
from src.db.turbopuffer_client import TurbopufferClient
from src.memory.vector_store import VectorSearchResult, VectorStore


def _score_from_dist(dist: float) -> float:
    # Convert distance-like values to a bounded score where larger is better.
    return 1.0 / (1.0 + max(0.0, float(dist)))


def _vector_schema() -> Dict[str, Any]:
    dims = int(config.turbopuffer.embedding_dimensions or 768)
    return {
        "vector": {"type": f"[{dims}]f32", "ann": True},
        "memory_id": {"type": "string"},
        "user_id": {"type": "string"},
        "memory_category": {"type": "string"},
        "memory_subtype": {"type": "string"},
        "importance": {"type": "float"},
        "created_at": {"type": "string"},
        "deleted": {"type": "int"},
    }


class TurbopufferVectorStore(VectorStore):
    """Vector search and embedding updates against Turbopuffer namespace."""

    def __init__(self):
        self._client = TurbopufferClient()
        self._namespace = config.turbopuffer.long_term_namespace

    def upsert_embeddings(
        self,
        items: Sequence[Tuple[str, Sequence[float], Dict[str, Any]]],
    ) -> None:
        if not items:
            return
        rows: List[Dict[str, Any]] = []
        for memory_id, embedding, metadata in items:
            row = {"id": memory_id, "vector": list(embedding)}
            row.update(metadata or {})
            rows.append(row)
        self._client.write(
            self._namespace,
            upsert_rows=rows,
            distance_metric="cosine_distance",
            schema=_vector_schema(),
        )

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        predicates: List[List[Any]] = [["deleted", "Eq", 0]]
        if filters and filters.get("user_id"):
            predicates.append(["user_id", "Eq", filters["user_id"]])

        query_resp = self._client.query(
            self._namespace,
            rank_by=["vector", "ANN", list(query_embedding)],
            top_k=top_k,
            filters=["And", predicates] if len(predicates) > 1 else predicates[0],
            include_attributes=[
                "memory_id",
                "user_id",
                "memory_category",
                "memory_subtype",
                "importance",
                "created_at",
            ],
        )
        rows = query_resp.get("rows", [])
        out: List[VectorSearchResult] = []
        for row in rows:
            attributes = row.get("attributes") if isinstance(row, dict) else None
            if not isinstance(attributes, dict):
                attributes = dict(row)
            dist = row.get("$dist", 0.0)
            out.append(
                VectorSearchResult(
                    memory_id=str(attributes.get("memory_id") or row.get("id")),
                    score=_score_from_dist(float(dist)),
                    metadata={
                        "user_id": attributes.get("user_id"),
                        "memory_category": attributes.get("memory_category"),
                        "memory_subtype": attributes.get("memory_subtype"),
                        "importance": attributes.get("importance"),
                        "created_at": attributes.get("created_at"),
                    },
                )
            )
        return out

    def delete(self, ids: Sequence[str]) -> None:
        if not ids:
            return
        self._client.write(self._namespace, deletes=[str(v) for v in ids])
