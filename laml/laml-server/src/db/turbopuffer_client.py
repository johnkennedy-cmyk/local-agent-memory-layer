"""Minimal Turbopuffer REST client wrapper for LAML backends."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from src.config import config


class TurbopufferClient:
    """Thin REST wrapper around Turbopuffer namespace write/query endpoints."""

    def __init__(self) -> None:
        tpuf = config.turbopuffer
        if not tpuf.api_key:
            raise ValueError("TURBOPUFFER_API_KEY is required when vector backend=turbopuffer")
        self._base_url = tpuf.base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {tpuf.api_key}",
            "Content-Type": "application/json",
        }

    def write(
        self,
        namespace: str,
        *,
        upsert_rows: Optional[List[Dict[str, Any]]] = None,
        deletes: Optional[List[str]] = None,
        distance_metric: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if upsert_rows is not None:
            payload["upsert_rows"] = upsert_rows
        if deletes is not None:
            payload["deletes"] = deletes
        if distance_metric is not None:
            payload["distance_metric"] = distance_metric
        if schema is not None:
            payload["schema"] = schema
        response = requests.post(
            f"{self._base_url}/v2/namespaces/{namespace}",
            json=payload,
            headers=self._headers,
            timeout=30,
        )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def query(
        self,
        namespace: str,
        *,
        rank_by: List[Any],
        top_k: int,
        filters: Optional[List[Any]] = None,
        include_attributes: Optional[List[str]] = None,
        include_vectors: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "rank_by": rank_by,
            "top_k": top_k,
        }
        if filters is not None:
            payload["filters"] = filters
        if include_attributes is not None:
            payload["include_attributes"] = include_attributes
        if include_vectors:
            payload["include_vectors"] = True
        response = requests.post(
            f"{self._base_url}/v2/namespaces/{namespace}/query",
            json=payload,
            headers=self._headers,
            timeout=30,
        )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def metadata(self, namespace: str) -> Dict[str, Any]:
        response = requests.get(
            f"{self._base_url}/v1/namespaces/{namespace}/metadata",
            headers=self._headers,
            timeout=30,
        )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()
