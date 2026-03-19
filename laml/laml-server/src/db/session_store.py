"""Backend-agnostic session store interfaces and Firebolt implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Dict, Any

from src.db.client import db


@dataclass
class SessionRecord:
  """In-memory representation of a session_contexts row."""
  session_id: str
  user_id: str
  org_id: Optional[str]
  total_tokens: int
  max_tokens: int


class SessionStore(Protocol):
  """Abstract interface for session persistence."""

  def get_session(self, session_id: str) -> Optional[SessionRecord]:
    ...

  def create_session(
    self,
    session_id: str,
    user_id: str,
    org_id: Optional[str],
    max_tokens: int,
  ) -> SessionRecord:
    ...

  def touch_session(self, session_id: str) -> None:
    """Update last_activity for an existing session."""
    ...

  def update_total_tokens(self, session_id: str, new_total: int) -> None:
    ...

  def increment_total_tokens(self, session_id: str, delta: int) -> None:
    ...

  def count_all(self) -> int:
    """Total number of sessions (for stats)."""
    ...


class FireboltSessionStore(SessionStore):
  """Firebolt-backed implementation using session_contexts table."""

  def get_session(self, session_id: str) -> Optional[SessionRecord]:
    rows = db.execute(
      """
      SELECT session_id, user_id, org_id, total_tokens, max_tokens
      FROM session_contexts
      WHERE session_id = ?
      """,
      (session_id,),
    )
    if not rows:
      return None
    sid, user_id, org_id, total_tokens, max_tokens = rows[0]
    return SessionRecord(
      session_id=sid,
      user_id=user_id,
      org_id=org_id,
      total_tokens=int(total_tokens or 0),
      max_tokens=int(max_tokens or 0),
    )

  def create_session(
    self,
    session_id: str,
    user_id: str,
    org_id: Optional[str],
    max_tokens: int,
  ) -> SessionRecord:
    db.execute(
      """
      INSERT INTO session_contexts (session_id, user_id, org_id, max_tokens, total_tokens)
      VALUES (?, ?, ?, ?, 0)
      """,
      (session_id, user_id, org_id, max_tokens),
    )
    return SessionRecord(
      session_id=session_id,
      user_id=user_id,
      org_id=org_id,
      total_tokens=0,
      max_tokens=max_tokens,
    )

  def touch_session(self, session_id: str) -> None:
    db.execute(
      "UPDATE session_contexts SET last_activity = CURRENT_TIMESTAMP() WHERE session_id = ?",
      (session_id,),
    )

  def update_total_tokens(self, session_id: str, new_total: int) -> None:
    db.execute(
      "UPDATE session_contexts SET total_tokens = ? WHERE session_id = ?",
      (new_total, session_id),
    )

  def increment_total_tokens(self, session_id: str, delta: int) -> None:
    db.execute(
      """
      UPDATE session_contexts
      SET total_tokens = total_tokens + ?, last_activity = CURRENT_TIMESTAMP()
      WHERE session_id = ?
      """,
      (delta, session_id),
    )

  def count_all(self) -> int:
    rows = db.execute("SELECT COUNT(*) FROM session_contexts")
    return int(rows[0][0]) if rows else 0
