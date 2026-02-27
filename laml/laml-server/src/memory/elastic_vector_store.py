"""Elasticsearch-backed VectorStore implementation for LAML long-term memory."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.config import config
from src.memory.vector_store import VectorSearchResult, VectorStore


def _get_es_client():
    from elasticsearch import Elasticsearch

    es_config = config.elastic
    kwargs = {
        "hosts": [es_config.url],
        "verify_certs": es_config.ssl_verify,
    }
    if es_config.api_key:
        kwargs["api_key"] = es_config.api_key
    elif es_config.username and es_config.password:
        kwargs["basic_auth"] = (es_config.username, es_config.password)
    return Elasticsearch(**kwargs)


class ElasticVectorStore(VectorStore):
    """
    VectorStore implementation backed by Elasticsearch kNN.

    Uses the same index as ElasticMemoryRepository (laml_long_term_memories)
    with a dense_vector field for cosine similarity search.
    """

    def __init__(self):
        self._client = _get_es_client()
        self._index = config.elastic.index_name

    def upsert_embeddings(
        self,
        items: Sequence[Tuple[str, Sequence[float], Dict[str, Any]]],
    ) -> None:
        """Update only the embedding (and optionally metadata) for existing documents."""
        for memory_id, embedding, _metadata in items:
            self._client.update(
                index=self._index,
                id=memory_id,
                body={
                    "doc": {"embedding": list(embedding), "updated_at": _now_iso()},
                    "doc_as_upsert": False,
                },
                refresh=True,
            )

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """kNN search with optional user_id filter; excludes soft-deleted."""
        must = [{"bool": {"must_not": {"exists": {"field": "deleted_at"}}}}]
        if filters and filters.get("user_id"):
            must.append({"term": {"user_id": filters["user_id"]}})

        body = {
            "knn": {
                "field": "embedding",
                "query_vector": list(query_embedding),
                "k": top_k,
                "num_candidates": max(top_k * 2, 50),
            },
            "query": {"bool": {"must": must}},
            "size": top_k,
            "_source": ["memory_id", "user_id", "memory_category", "memory_subtype", "importance", "created_at"],
        }
        resp = self._client.search(index=self._index, body=body)
        results = []
        for hit in resp.get("hits", {}).get("hits", []):
            score = float(hit.get("_score", 0.0))
            src = hit.get("_source", {})
            # Elasticsearch kNN with cosine can return _score in a different form; use 1/(1+distance) or raw
            results.append(
                VectorSearchResult(
                    memory_id=src.get("memory_id", hit["_id"]),
                    score=score,
                    metadata={
                        "user_id": src.get("user_id"),
                        "memory_category": src.get("memory_category"),
                        "memory_subtype": src.get("memory_subtype"),
                        "importance": src.get("importance"),
                        "created_at": src.get("created_at"),
                    },
                )
            )
        return results

    def delete(self, ids: Sequence[str]) -> None:
        """Soft-delete: set deleted_at for the given memory ids."""
        now = _now_iso()
        for memory_id in ids:
            self._client.update(
                index=self._index,
                id=memory_id,
                body={"doc": {"deleted_at": now}, "doc_as_upsert": False},
                refresh=True,
            )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
