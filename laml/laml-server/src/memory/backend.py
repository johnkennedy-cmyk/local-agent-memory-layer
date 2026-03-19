"""Pluggable vector and long-term memory backend with optional dual-write."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from src.config import config
from src.memory.vector_store import VectorStore


class MemoryRepository(Protocol):
    """Protocol for long-term memory CRUD (used by longterm_memory tools)."""

    def insert(self, doc: Dict[str, Any]) -> None:
        ...

    def update(self, memory_id: str, user_id: str, fields: Dict[str, Any]) -> None:
        ...

    def get_by_id(
        self,
        memory_id: str,
        user_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        ...

    def get_many_by_ids(
        self, ids: List[str], user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        ...

    def count_for_user(self, user_id: str, include_deleted: bool = False) -> int:
        ...

    def soft_delete(self, memory_id: str, user_id: str) -> None:
        ...

    def hard_delete(self, memory_id: str, user_id: str) -> None:
        ...

    def delete_all_for_user(self, user_id: str) -> None:
        ...

    def increment_access_count(self, memory_id: str) -> None:
        ...

    def count_total(self, include_deleted: bool = False) -> int:
        ...


class FireboltMemoryRepository:
    """Memory repository that uses Firebolt db.execute for long_term_memories."""

    def __init__(self):
        from src.db.client import db
        self._db = db

    def insert(self, doc: Dict[str, Any]) -> None:
        self._db.execute(
            """
            INSERT INTO long_term_memories (
                memory_id, user_id, memory_category, memory_subtype,
                content, summary, embedding, entities, importance,
                event_time, metadata, is_temporal, source_session, source_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc["memory_id"],
                doc["user_id"],
                doc["memory_category"],
                doc["memory_subtype"],
                doc["content"],
                doc.get("summary"),
                list(doc["embedding"]),
                doc.get("entities") or [],
                doc.get("importance", 0.5),
                doc.get("event_time"),
                doc.get("metadata"),
                doc.get("is_temporal", False),
                doc.get("source_session"),
                doc.get("source_type", "conversation"),
            ),
        )

    def update(self, memory_id: str, user_id: str, fields: Dict[str, Any]) -> None:
        updates = []
        params = []
        for k, v in fields.items():
            if k in ("updated_at",):
                continue
            updates.append(f"{k} = ?")
            if k == "embedding":
                params.append(list(v))
            else:
                params.append(v)
        if not updates:
            return
        params.extend([memory_id, user_id])
        self._db.execute(
            f"UPDATE long_term_memories SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP() WHERE memory_id = ? AND user_id = ?",
            tuple(params),
        )

    def get_by_id(
        self,
        memory_id: str,
        user_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if include_deleted:
            q = "SELECT user_id FROM long_term_memories WHERE memory_id = ?"
            params = (memory_id,)
        else:
            q = "SELECT user_id FROM long_term_memories WHERE memory_id = ? AND deleted_at IS NULL"
            params = (memory_id,)
        rows = self._db.execute(q, params)
        if not rows:
            return None
        if user_id is not None and rows[0][0] != user_id:
            return None
        return {"user_id": rows[0][0]}

    def get_many_by_ids(
        self, ids: List[str], user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join(["?"] * len(ids))
        if user_id is not None:
            q = f"""
                SELECT memory_id, content, summary, memory_category, memory_subtype,
                       entities, importance, access_count, created_at, metadata
                FROM long_term_memories
                WHERE user_id = ? AND memory_id IN ({placeholders}) AND deleted_at IS NULL
            """
            params = (user_id, *ids)
        else:
            q = f"""
                SELECT memory_id, content, summary, memory_category, memory_subtype,
                       entities, importance, access_count, created_at, metadata
                FROM long_term_memories
                WHERE memory_id IN ({placeholders}) AND deleted_at IS NULL
            """
            params = tuple(ids)
        rows = self._db.execute(q, params)
        result = []
        for row in rows:
            result.append({
                "memory_id": row[0],
                "content": row[1],
                "summary": row[2],
                "memory_category": row[3],
                "memory_subtype": row[4],
                "entities": row[5] or [],
                "importance": row[6],
                "access_count": row[7],
                "created_at": row[8],
                "metadata": row[9],
            })
        return result

    def count_for_user(self, user_id: str, include_deleted: bool = False) -> int:
        if include_deleted:
            q = "SELECT COUNT(*) FROM long_term_memories WHERE user_id = ?"
            params = (user_id,)
        else:
            q = "SELECT COUNT(*) FROM long_term_memories WHERE user_id = ? AND deleted_at IS NULL"
            params = (user_id,)
        rows = self._db.execute(q, params)
        return int(rows[0][0]) if rows else 0

    def soft_delete(self, memory_id: str, user_id: str) -> None:
        self._db.execute(
            "UPDATE long_term_memories SET deleted_at = CURRENT_TIMESTAMP() WHERE memory_id = ? AND user_id = ?",
            (memory_id, user_id),
        )

    def hard_delete(self, memory_id: str, user_id: str) -> None:
        self._db.execute(
            "DELETE FROM long_term_memories WHERE memory_id = ? AND user_id = ?",
            (memory_id, user_id),
        )

    def delete_all_for_user(self, user_id: str) -> None:
        self._db.execute("DELETE FROM long_term_memories WHERE user_id = ?", (user_id,))

    def count_total(self, include_deleted: bool = False) -> int:
        if include_deleted:
            q = "SELECT COUNT(*) FROM long_term_memories"
            params = ()
        else:
            q = "SELECT COUNT(*) FROM long_term_memories WHERE deleted_at IS NULL"
            params = ()
        rows = self._db.execute(q, params)
        return int(rows[0][0]) if rows else 0

    def increment_access_count(self, memory_id: str) -> None:
        self._db.execute(
            """
            UPDATE long_term_memories
            SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP()
            WHERE memory_id = ?
            """,
            (memory_id,),
        )

    def get_category_counts(self) -> Dict[str, int]:
        """Return counts per memory_category (non-deleted)."""
        rows = self._db.execute(
            """
            SELECT memory_category, COUNT(*) as cnt
            FROM long_term_memories
            WHERE deleted_at IS NULL
            GROUP BY memory_category
            """
        )
        return {row[0]: row[1] for row in rows}

    def get_top_accessed(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return top accessed memories for stats."""
        rows = self._db.execute(
            f"""
            SELECT memory_id, memory_category, access_count, importance, content
            FROM long_term_memories
            WHERE deleted_at IS NULL
            ORDER BY access_count DESC
            LIMIT {int(limit)}
            """
        )
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "memory_id": row[0],
                    "memory_category": row[1],
                    "access_count": row[2],
                    "importance": row[3],
                    "content": row[4] or "",
                }
            )
        return result


class DualWriteVectorStore(VectorStore):
    """Write-through wrapper: read from primary, mirror writes/deletes to secondary."""

    def __init__(self, primary: VectorStore, secondary: VectorStore):
        self._primary = primary
        self._secondary = secondary

    def upsert_embeddings(
        self,
        items: List[tuple[str, list[float], dict[str, Any]]],
    ) -> None:
        self._primary.upsert_embeddings(items)
        self._secondary.upsert_embeddings(items)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ):
        return self._primary.search(query_embedding=query_embedding, top_k=top_k, filters=filters)

    def delete(self, ids: list[str]) -> None:
        self._primary.delete(ids)
        self._secondary.delete(ids)


class DualWriteMemoryRepository:
    """Write-through wrapper: read from primary, mirror writes/deletes to secondary."""

    def __init__(self, primary: MemoryRepository, secondary: MemoryRepository):
        self._primary = primary
        self._secondary = secondary

    def insert(self, doc: Dict[str, Any]) -> None:
        self._primary.insert(doc)
        self._secondary.insert(doc)

    def update(self, memory_id: str, user_id: str, fields: Dict[str, Any]) -> None:
        self._primary.update(memory_id, user_id, fields)
        self._secondary.update(memory_id, user_id, fields)

    def get_by_id(
        self,
        memory_id: str,
        user_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        return self._primary.get_by_id(memory_id, user_id=user_id, include_deleted=include_deleted)

    def get_many_by_ids(
        self, ids: List[str], user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return self._primary.get_many_by_ids(ids, user_id=user_id)

    def count_for_user(self, user_id: str, include_deleted: bool = False) -> int:
        return self._primary.count_for_user(user_id, include_deleted=include_deleted)

    def soft_delete(self, memory_id: str, user_id: str) -> None:
        self._primary.soft_delete(memory_id, user_id)
        self._secondary.soft_delete(memory_id, user_id)

    def hard_delete(self, memory_id: str, user_id: str) -> None:
        self._primary.hard_delete(memory_id, user_id)
        self._secondary.hard_delete(memory_id, user_id)

    def delete_all_for_user(self, user_id: str) -> None:
        self._primary.delete_all_for_user(user_id)
        self._secondary.delete_all_for_user(user_id)

    def increment_access_count(self, memory_id: str) -> None:
        self._primary.increment_access_count(memory_id)
        self._secondary.increment_access_count(memory_id)

    def count_total(self, include_deleted: bool = False) -> int:
        return self._primary.count_total(include_deleted=include_deleted)

    def get_category_counts(self) -> Dict[str, int]:
        getter = getattr(self._primary, "get_category_counts", None)
        if getter is None:
            return {}
        return getter()

    def get_top_accessed(self, limit: int = 5) -> List[Dict[str, Any]]:
        getter = getattr(self._primary, "get_top_accessed", None)
        if getter is None:
            return []
        return getter(limit=limit)

    def get_storage_bytes(self) -> int:
        getter = getattr(self._primary, "get_storage_bytes", None)
        if getter is None:
            return 0
        return int(getter())


def _vector_store_for_backend(backend: str) -> VectorStore:
    if backend == "elastic":
        from src.memory.elastic_vector_store import ElasticVectorStore

        return ElasticVectorStore()
    if backend == "clickhouse":
        from src.memory.clickhouse_vector_store import ClickHouseVectorStore

        return ClickHouseVectorStore()
    if backend == "turbopuffer":
        from src.memory.turbopuffer_vector_store import TurbopufferVectorStore

        return TurbopufferVectorStore()
    from src.memory.firebolt_vector_store import FireboltVectorStore

    return FireboltVectorStore()


def _memory_repo_for_backend(backend: str) -> MemoryRepository:
    if backend == "elastic":
        from src.memory.elastic_memory_repo import ElasticMemoryRepository

        return ElasticMemoryRepository()
    if backend == "clickhouse":
        from src.memory.clickhouse_memory_repo import ClickHouseMemoryRepository

        return ClickHouseMemoryRepository()
    if backend == "turbopuffer":
        from src.memory.turbopuffer_memory_repo import TurbopufferMemoryRepository

        return TurbopufferMemoryRepository()
    return FireboltMemoryRepository()


def get_vector_store() -> VectorStore:
    """Return configured vector store; optionally mirror writes to a secondary backend."""
    primary = _vector_store_for_backend(config.vector_backend)
    if config.dual_write_backend:
        secondary = _vector_store_for_backend(config.dual_write_backend)
        return DualWriteVectorStore(primary=primary, secondary=secondary)
    return primary


def get_memory_repository() -> MemoryRepository:
    """Return configured memory repository; optionally mirror writes to secondary backend."""
    primary = _memory_repo_for_backend(config.vector_backend)
    if config.dual_write_backend:
        secondary = _memory_repo_for_backend(config.dual_write_backend)
        return DualWriteMemoryRepository(primary=primary, secondary=secondary)
    return primary
