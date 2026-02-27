from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple


@dataclass
class VectorSearchResult:
    """Result item from a vector similarity search."""

    memory_id: str
    score: float
    metadata: Dict[str, Any]


class VectorStore(ABC):
    """Abstract interface for pluggable vector backends."""

    @abstractmethod
    def upsert_embeddings(
        self,
        items: Sequence[Tuple[str, Sequence[float], Dict[str, Any]]],
    ) -> None:
        """
        Upsert embeddings into the vector store.

        Each item is (id, embedding, metadata).
        """

    @abstractmethod
    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """
        Perform a similarity search against stored embeddings.
        """

    @abstractmethod
    def delete(self, ids: Sequence[str]) -> None:
        """Delete embeddings for the given ids (or soft-delete, backend dependent)."""


class VectorStoreFactory(Protocol):
    """Factory protocol for constructing a VectorStore."""

    def create(self) -> VectorStore:  # pragma: no cover - simple protocol
        ...
