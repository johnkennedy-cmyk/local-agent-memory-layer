"""Working memory MCP tools."""

import json
import uuid
from typing import Optional
from mcp.server.fastmcp import FastMCP

from src.db.client import db
from src.llm.embeddings import embedding_service


def register_working_memory_tools(mcp: FastMCP):
    """Register working memory tools with the MCP server."""

    @mcp.tool()
    async def init_session(
        user_id: str,
        session_id: Optional[str] = None,
        org_id: Optional[str] = None,
        max_tokens: int = 8000
    ) -> str:
        """
        Initialize or resume a memory session.

        Args:
            user_id: Unique identifier for the user
            session_id: Optional session ID (generates UUID if not provided)
            org_id: Optional organization ID for multi-tenant isolation
            max_tokens: Maximum tokens for working memory (default: 8000)

        Returns:
            JSON with session_id and whether it was newly created
        """
        sid = session_id or str(uuid.uuid4())

        # Check if session exists
        existing = db.execute(
            "SELECT session_id, total_tokens, max_tokens FROM session_contexts WHERE session_id = ?",
            (sid,)
        )

        if existing:
            # Update last activity
            db.execute(
                "UPDATE session_contexts SET last_activity = CURRENT_TIMESTAMP() WHERE session_id = ?",
                (sid,)
            )
            return json.dumps({
                "session_id": sid,
                "created": False,
                "total_tokens": existing[0][1],
                "max_tokens": existing[0][2]
            })

        # Create new session
        db.execute("""
            INSERT INTO session_contexts (session_id, user_id, org_id, max_tokens, total_tokens)
            VALUES (?, ?, ?, ?, 0)
        """, (sid, user_id, org_id, max_tokens))

        return json.dumps({
            "session_id": sid,
            "created": True,
            "total_tokens": 0,
            "max_tokens": max_tokens
        })

    @mcp.tool()
    async def add_to_working_memory(
        session_id: str,
        content: str,
        content_type: str = "message",
        pinned: bool = False,
        relevance_score: float = 1.0
    ) -> str:
        """
        Add an item to working memory.

        Args:
            session_id: The session to add to
            content: The content to store
            content_type: Type of content ('message', 'task_state', 'scratchpad', 'retrieved_memory')
            pinned: If True, item won't be evicted automatically
            relevance_score: Initial relevance score (0.0 to 1.0)

        Returns:
            JSON with item_id, token_count, and any evicted items
        """
        item_id = str(uuid.uuid4())
        token_count = embedding_service.count_tokens(content)

        # Get session info
        session = db.execute(
            "SELECT user_id, total_tokens, max_tokens FROM session_contexts WHERE session_id = ?",
            (session_id,)
        )

        if not session:
            return json.dumps({"error": f"Session not found: {session_id}"})

        user_id, total_tokens, max_tokens = session[0]

        # Get next sequence number
        result = db.execute(
            "SELECT COALESCE(MAX(sequence_num), 0) + 1 FROM working_memory_items WHERE session_id = ?",
            (session_id,)
        )
        seq_num = result[0][0] if result else 1

        # Check if we need to evict items
        evicted_items = []
        if total_tokens + token_count > max_tokens:
            evicted_items = await _evict_working_memory(
                session_id,
                user_id,
                token_count - (max_tokens - total_tokens)
            )

        # Insert item
        db.execute("""
            INSERT INTO working_memory_items
            (item_id, session_id, user_id, content_type, content, token_count,
             relevance_score, pinned, sequence_num)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (item_id, session_id, user_id, content_type, content, token_count,
              relevance_score, pinned, seq_num))

        # Update session token count
        db.execute("""
            UPDATE session_contexts
            SET total_tokens = total_tokens + ?, last_activity = CURRENT_TIMESTAMP()
            WHERE session_id = ?
        """, (token_count, session_id))

        return json.dumps({
            "item_id": item_id,
            "token_count": token_count,
            "sequence_num": seq_num,
            "evicted_items": evicted_items
        })

    @mcp.tool()
    async def get_working_memory(
        session_id: str,
        token_budget: Optional[int] = None,
        include_types: Optional[str] = None
    ) -> str:
        """
        Retrieve current working memory state.

        Args:
            session_id: The session to retrieve
            token_budget: Maximum tokens to return (uses session max if not specified)
            include_types: Comma-separated content types to include (e.g., 'message,task_state')

        Returns:
            JSON with items, total_tokens, and truncation status
        """
        # Get session info
        session = db.execute(
            "SELECT max_tokens, total_tokens FROM session_contexts WHERE session_id = ?",
            (session_id,)
        )

        if not session:
            return json.dumps({"error": f"Session not found: {session_id}"})

        max_tokens, total_tokens = session[0]
        budget = token_budget or max_tokens

        # Build query
        query = """
            SELECT item_id, content_type, content, token_count, pinned,
                   relevance_score, sequence_num
            FROM working_memory_items
            WHERE session_id = ?
        """
        params = [session_id]

        if include_types:
            types = [t.strip() for t in include_types.split(",")]
            placeholders = ",".join(["?" for _ in types])
            query += f" AND content_type IN ({placeholders})"
            params.extend(types)

        query += " ORDER BY pinned DESC, relevance_score DESC, sequence_num DESC"

        items = db.execute(query, tuple(params))

        # Collect items within budget
        result_items = []
        used_tokens = 0

        for item in items:
            item_tokens = item[3]
            if used_tokens + item_tokens <= budget:
                result_items.append({
                    "item_id": item[0],
                    "content_type": item[1],
                    "content": item[2],
                    "token_count": item_tokens,
                    "pinned": bool(item[4]),
                    "relevance_score": item[5],
                    "sequence_num": item[6]
                })
                used_tokens += item_tokens

        return json.dumps({
            "items": result_items,
            "total_tokens": used_tokens,
            "session_total_tokens": total_tokens,
            "truncated": used_tokens < total_tokens,
            "item_count": len(result_items)
        })

    @mcp.tool()
    async def update_working_memory_item(
        item_id: str,
        session_id: str,
        pinned: Optional[bool] = None,
        relevance_score: Optional[float] = None
    ) -> str:
        """
        Update a working memory item's properties.

        Args:
            item_id: The item to update
            session_id: The session containing the item
            pinned: New pinned status
            relevance_score: New relevance score

        Returns:
            JSON with success status
        """
        updates = []
        params = []

        if pinned is not None:
            updates.append("pinned = ?")
            params.append(pinned)

        if relevance_score is not None:
            updates.append("relevance_score = ?")
            params.append(relevance_score)

        if not updates:
            return json.dumps({"error": "No updates provided"})

        updates.append("last_accessed = CURRENT_TIMESTAMP()")
        params.extend([item_id, session_id])

        db.execute(f"""
            UPDATE working_memory_items
            SET {", ".join(updates)}
            WHERE item_id = ? AND session_id = ?
        """, tuple(params))

        return json.dumps({"success": True, "item_id": item_id})

    @mcp.tool()
    async def clear_working_memory(
        session_id: str,
        preserve_pinned: bool = True
    ) -> str:
        """
        Clear working memory for a session.

        Args:
            session_id: The session to clear
            preserve_pinned: If True, keep pinned items

        Returns:
            JSON with number of items cleared
        """
        if preserve_pinned:
            # Get count of items to delete
            count_result = db.execute(
                "SELECT COUNT(*) FROM working_memory_items WHERE session_id = ? AND pinned = FALSE",
                (session_id,)
            )
            count = count_result[0][0] if count_result else 0

            # Delete non-pinned items
            db.execute(
                "DELETE FROM working_memory_items WHERE session_id = ? AND pinned = FALSE",
                (session_id,)
            )

            # Recalculate token count
            token_result = db.execute(
                "SELECT COALESCE(SUM(token_count), 0) FROM working_memory_items WHERE session_id = ?",
                (session_id,)
            )
            new_total = token_result[0][0] if token_result else 0
        else:
            # Get count of all items
            count_result = db.execute(
                "SELECT COUNT(*) FROM working_memory_items WHERE session_id = ?",
                (session_id,)
            )
            count = count_result[0][0] if count_result else 0

            # Delete all items
            db.execute(
                "DELETE FROM working_memory_items WHERE session_id = ?",
                (session_id,)
            )
            new_total = 0

        # Update session token count
        db.execute(
            "UPDATE session_contexts SET total_tokens = ? WHERE session_id = ?",
            (new_total, session_id)
        )

        return json.dumps({
            "success": True,
            "items_cleared": count,
            "remaining_tokens": new_total
        })


async def _evict_working_memory(session_id: str, user_id: str, tokens_needed: int) -> list:
    """
    Evict items from working memory to free up space.

    Strategy: Evict lowest relevance non-pinned items first.
    """
    # Get eviction candidates (non-pinned, ordered by relevance then age)
    candidates = db.execute("""
        SELECT item_id, token_count, relevance_score
        FROM working_memory_items
        WHERE session_id = ? AND pinned = FALSE
        ORDER BY relevance_score ASC, sequence_num ASC
    """, (session_id,))

    evicted = []
    freed_tokens = 0

    for item in candidates:
        if freed_tokens >= tokens_needed:
            break

        item_id, token_count, _ = item

        # Delete the item
        db.execute(
            "DELETE FROM working_memory_items WHERE item_id = ?",
            (item_id,)
        )

        evicted.append(item_id)
        freed_tokens += token_count

    # Update session token count
    if evicted:
        db.execute("""
            UPDATE session_contexts
            SET total_tokens = total_tokens - ?
            WHERE session_id = ?
        """, (freed_tokens, session_id))

    return evicted
