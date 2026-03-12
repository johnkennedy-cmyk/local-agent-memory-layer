"""Elasticsearch-backed working memory store (when vector backend=elastic)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from src.config import config
from src.db.working_memory_store import WorkingMemoryStore, WorkingMemoryItem


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _source_to_item(source: dict, item_id: str) -> WorkingMemoryItem:
    return WorkingMemoryItem(
        item_id=item_id,
        session_id=source.get("session_id", ""),
        user_id=source.get("user_id", ""),
        content_type=source.get("content_type", "message"),
        content=source.get("content", ""),
        token_count=int(source.get("token_count", 0)),
        pinned=bool(source.get("pinned", False)),
        relevance_score=float(source.get("relevance_score", 1.0)),
        sequence_num=int(source.get("sequence_num", 0)),
    )


class WorkingMemoryStoreElastic(WorkingMemoryStore):
    """Elasticsearch-backed working memory store using laml_working_memory index."""

    def __init__(self):
        self._client = _get_es_client()
        self._index = config.elastic.working_memory_index

    def get_next_sequence_num(self, session_id: str) -> int:
        resp = self._client.search(
            index=self._index,
            body={
                "size": 0,
                "query": {"term": {"session_id": session_id}},
                "aggs": {"max_seq": {"max": {"field": "sequence_num"}}},
            },
        )
        agg = resp.get("aggregations", {}).get("max_seq", {})
        val = agg.get("value")
        return int(val) + 1 if val is not None else 1

    def insert_item(self, item: WorkingMemoryItem) -> None:
        now = _now_iso()
        body = {
            "item_id": item.item_id,
            "session_id": item.session_id,
            "user_id": item.user_id,
            "content_type": item.content_type,
            "content": item.content,
            "token_count": item.token_count,
            "pinned": item.pinned,
            "relevance_score": item.relevance_score,
            "sequence_num": item.sequence_num,
            "created_at": now,
            "last_accessed": now,
        }
        self._client.index(
            index=self._index,
            id=item.item_id,
            document=body,
            refresh=True,
        )

    def get_items_for_session(
        self,
        session_id: str,
        include_types: Optional[List[str]] = None,
    ) -> List[WorkingMemoryItem]:
        must = [{"term": {"session_id": session_id}}]
        if include_types:
            must.append({"terms": {"content_type": include_types}})
        resp = self._client.search(
            index=self._index,
            body={
                "size": 10000,
                "query": {"bool": {"must": must}},
                "sort": [
                    {"pinned": {"order": "desc"}},
                    {"relevance_score": {"order": "desc"}},
                    {"sequence_num": {"order": "desc"}},
                ],
            },
        )
        items = []
        for hit in resp.get("hits", {}).get("hits", []):
            items.append(_source_to_item(hit["_source"], hit["_id"]))
        return items

    def count_items(
        self,
        session_id: str,
        pinned_only: Optional[bool] = None,
    ) -> int:
        must = [{"term": {"session_id": session_id}}]
        if pinned_only is not None:
            must.append({"term": {"pinned": pinned_only}})
        resp = self._client.count(
            index=self._index,
            body={"query": {"bool": {"must": must}}},
        )
        return int(resp.get("count", 0))

    def delete_items(
        self,
        session_id: str,
        pinned_only: Optional[bool] = None,
    ) -> None:
        must = [{"term": {"session_id": session_id}}]
        if pinned_only is not None:
            must.append({"term": {"pinned": pinned_only}})
        self._client.delete_by_query(
            index=self._index,
            body={"query": {"bool": {"must": must}}},
            refresh=True,
        )

    def sum_tokens(self, session_id: str) -> int:
        resp = self._client.search(
            index=self._index,
            body={
                "size": 0,
                "query": {"term": {"session_id": session_id}},
                "aggs": {"total_tokens": {"sum": {"field": "token_count"}}},
            },
        )
        agg = resp.get("aggregations", {}).get("total_tokens", {})
        val = agg.get("value")
        return int(val) if val is not None else 0

    def count_all(self) -> int:
        resp = self._client.count(index=self._index, body={"query": {"match_all": {}}})
        return int(resp.get("count", 0))

    def sum_tokens_all(self) -> int:
        resp = self._client.search(
            index=self._index,
            body={
                "size": 0,
                "aggs": {"total_tokens": {"sum": {"field": "token_count"}}},
            },
        )
        agg = resp.get("aggregations", {}).get("total_tokens", {})
        val = agg.get("value")
        return int(val) if val is not None else 0

    def update_item_flags(
        self,
        item_id: str,
        session_id: str,
        pinned: Optional[bool],
        relevance_score: Optional[float],
    ) -> None:
        doc = {}
        if pinned is not None:
            doc["pinned"] = pinned
        if relevance_score is not None:
            doc["relevance_score"] = relevance_score
        if not doc:
            return
        doc["last_accessed"] = _now_iso()
        self._client.update(
            index=self._index,
            id=item_id,
            body={"doc": doc},
            refresh=True,
        )

    def eviction_candidates(self, session_id: str) -> List[Tuple[str, int, float]]:
        resp = self._client.search(
            index=self._index,
            body={
                "size": 1000,
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"session_id": session_id}},
                            {"term": {"pinned": False}},
                        ]
                    }
                },
                "sort": [
                    {"relevance_score": {"order": "asc"}},
                    {"sequence_num": {"order": "asc"}},
                ],
                "_source": ["token_count", "relevance_score"],
            },
        )
        out = []
        for hit in resp.get("hits", {}).get("hits", []):
            src = hit["_source"]
            out.append((
                hit["_id"],
                int(src.get("token_count", 0)),
                float(src.get("relevance_score", 0)),
            ))
        return out

    def delete_item(self, item_id: str) -> None:
        self._client.delete(index=self._index, id=item_id, refresh=True)
