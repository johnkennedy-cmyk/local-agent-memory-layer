"""Backend-agnostic working memory store interfaces and Firebolt implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Dict, Any, Tuple

from src.db.client import db


@dataclass
class WorkingMemoryItem:
  item_id: str
  session_id: str
  user_id: str
  content_type: str
  content: str
  token_count: int
  pinned: bool
  relevance_score: float
  sequence_num: int


class WorkingMemoryStore(Protocol):
  """Abstract interface for working memory persistence."""

  def get_next_sequence_num(self, session_id: str) -> int:
    ...

  def insert_item(self, item: WorkingMemoryItem) -> None:
    ...

  def get_items_for_session(
    self,
    session_id: str,
    include_types: Optional[List[str]] = None,
  ) -> List[WorkingMemoryItem]:
    ...

  def count_items(
    self,
    session_id: str,
    pinned_only: Optional[bool] = None,
  ) -> int:
    ...

  def delete_items(
    self,
    session_id: str,
    pinned_only: Optional[bool] = None,
  ) -> None:
    ...

  def sum_tokens(self, session_id: str) -> int:
    ...

  def count_all(self) -> int:
    """Total number of working memory items across all sessions (for stats)."""
    ...

  def sum_tokens_all(self) -> int:
    """Sum of token_count across all items (for stats)."""
    ...

  def update_item_flags(
    self,
    item_id: str,
    session_id: str,
    pinned: Optional[bool],
    relevance_score: Optional[float],
  ) -> None:
    ...

  def eviction_candidates(self, session_id: str) -> List[Tuple[str, int, float]]:
    """Return (item_id, token_count, relevance_score) ordered for eviction."""
    ...

  def delete_item(self, item_id: str) -> None:
    ...


class FireboltWorkingMemoryStore(WorkingMemoryStore):
  """Firebolt-backed working memory store using working_memory_items table."""

  def get_next_sequence_num(self, session_id: str) -> int:
    rows = db.execute(
      "SELECT COALESCE(MAX(sequence_num), 0) + 1 FROM working_memory_items WHERE session_id = ?",
      (session_id,),
    )
    return int(rows[0][0]) if rows else 1

  def insert_item(self, item: WorkingMemoryItem) -> None:
    db.execute(
      """
      INSERT INTO working_memory_items
      (item_id, session_id, user_id, content_type, content, token_count,
       relevance_score, pinned, sequence_num)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      (
        item.item_id,
        item.session_id,
        item.user_id,
        item.content_type,
        item.content,
        item.token_count,
        item.relevance_score,
        item.pinned,
        item.sequence_num,
      ),
    )

  def get_items_for_session(
    self,
    session_id: str,
    include_types: Optional[List[str]] = None,
  ) -> List[WorkingMemoryItem]:
    query = """
      SELECT item_id, session_id, user_id, content_type, content,
             token_count, pinned, relevance_score, sequence_num
      FROM working_memory_items
      WHERE session_id = ?
    """
    params: List[Any] = [session_id]
    if include_types:
      placeholders = ",".join(["?"] * len(include_types))
      query += f" AND content_type IN ({placeholders})"
      params.extend(include_types)
    query += " ORDER BY pinned DESC, relevance_score DESC, sequence_num DESC"
    rows = db.execute(query, tuple(params))
    items: List[WorkingMemoryItem] = []
    for row in rows:
      items.append(
        WorkingMemoryItem(
          item_id=row[0],
          session_id=row[1],
          user_id=row[2],
          content_type=row[3],
          content=row[4],
          token_count=int(row[5]),
          pinned=bool(row[6]),
          relevance_score=float(row[7]),
          sequence_num=int(row[8]),
        )
      )
    return items

  def count_items(
    self,
    session_id: str,
    pinned_only: Optional[bool] = None,
  ) -> int:
    if pinned_only is None:
      q = "SELECT COUNT(*) FROM working_memory_items WHERE session_id = ?"
      params = (session_id,)
    else:
      q = "SELECT COUNT(*) FROM working_memory_items WHERE session_id = ? AND pinned = ?"
      params = (session_id, pinned_only)
    rows = db.execute(q, params)
    return int(rows[0][0]) if rows else 0

  def delete_items(
    self,
    session_id: str,
    pinned_only: Optional[bool] = None,
  ) -> None:
    if pinned_only is None:
      q = "DELETE FROM working_memory_items WHERE session_id = ?"
      params = (session_id,)
    else:
      q = "DELETE FROM working_memory_items WHERE session_id = ? AND pinned = ?"
      params = (session_id, pinned_only)
    db.execute(q, params)

  def sum_tokens(self, session_id: str) -> int:
    rows = db.execute(
      "SELECT COALESCE(SUM(token_count), 0) FROM working_memory_items WHERE session_id = ?",
      (session_id,),
    )
    return int(rows[0][0]) if rows else 0

  def count_all(self) -> int:
    rows = db.execute("SELECT COUNT(*) FROM working_memory_items")
    return int(rows[0][0]) if rows else 0

  def sum_tokens_all(self) -> int:
    rows = db.execute("SELECT COALESCE(SUM(token_count), 0) FROM working_memory_items")
    return int(rows[0][0]) if rows else 0

  def update_item_flags(
    self,
    item_id: str,
    session_id: str,
    pinned: Optional[bool],
    relevance_score: Optional[float],
  ) -> None:
    updates: List[str] = []
    params: List[Any] = []
    if pinned is not None:
      updates.append("pinned = ?")
      params.append(pinned)
    if relevance_score is not None:
      updates.append("relevance_score = ?")
      params.append(relevance_score)
    if not updates:
      return
    updates.append("last_accessed = CURRENT_TIMESTAMP()")
    params.extend([item_id, session_id])
    db.execute(
      f"""
      UPDATE working_memory_items
      SET {", ".join(updates)}
      WHERE item_id = ? AND session_id = ?
      """,
      tuple(params),
    )

  def eviction_candidates(self, session_id: str) -> List[Tuple[str, int, float]]:
    rows = db.execute(
      """
      SELECT item_id, token_count, relevance_score
      FROM working_memory_items
      WHERE session_id = ? AND pinned = FALSE
      ORDER BY relevance_score ASC, sequence_num ASC
      """,
      (session_id,),
    )
    return [(row[0], int(row[1]), float(row[2])) for row in rows]

  def delete_item(self, item_id: str) -> None:
    db.execute(
      "DELETE FROM working_memory_items WHERE item_id = ?",
      (item_id,),
    )

