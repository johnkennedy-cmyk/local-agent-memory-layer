"""Working memory MCP tools."""

import json
import uuid
from typing import Optional
from mcp.server.fastmcp import FastMCP

from src.db.backend_router import get_session_store, get_working_memory_store
from src.db.working_memory_store import WorkingMemoryItem
from src.llm.embeddings import embedding_service
from src.security import validate_content_for_storage


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
        session_store = get_session_store()

        existing = session_store.get_session(sid)
        if existing:
            session_store.touch_session(sid)
            return json.dumps({
                "session_id": sid,
                "created": False,
                "total_tokens": existing.total_tokens,
                "max_tokens": existing.max_tokens
            })

        session_store.create_session(sid, user_id, org_id, max_tokens)
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
        # Security check: validate content before storing
        is_safe, error_msg, violations = validate_content_for_storage(content)
        if not is_safe:
            return json.dumps({
                "error": "SECURITY_VIOLATION",
                "message": error_msg,
                "violations": [
                    {
                        "pattern": v.pattern_name,
                        "severity": v.severity,
                        "description": v.description
                    }
                    for v in violations
                ],
                "hint": "Sensitive data like API keys, passwords, and tokens should not be stored in working memory."
            })

        item_id = str(uuid.uuid4())
        token_count = embedding_service.count_tokens(content)

        session_store = get_session_store()
        wm_store = get_working_memory_store()

        session = session_store.get_session(session_id)
        if not session:
            return json.dumps({"error": f"Session not found: {session_id}"})

        user_id, total_tokens, max_tokens = session.user_id, session.total_tokens, session.max_tokens

        seq_num = wm_store.get_next_sequence_num(session_id)

        # Check if we need to evict items
        evicted_items = []
        if total_tokens + token_count > max_tokens:
            evicted_items = await _evict_working_memory(
                session_id,
                user_id,
                token_count - (max_tokens - total_tokens)
            )

        item = WorkingMemoryItem(
            item_id=item_id,
            session_id=session_id,
            user_id=user_id,
            content_type=content_type,
            content=content,
            token_count=token_count,
            pinned=pinned,
            relevance_score=relevance_score,
            sequence_num=seq_num,
        )
        wm_store.insert_item(item)
        session_store.increment_total_tokens(session_id, token_count)

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
        session_store = get_session_store()
        wm_store = get_working_memory_store()

        session = session_store.get_session(session_id)
        if not session:
            return json.dumps({"error": f"Session not found: {session_id}"})

        max_tokens, total_tokens = session.max_tokens, session.total_tokens
        budget = token_budget or max_tokens

        include_types_list = [t.strip() for t in include_types.split(",")] if include_types else None
        items = wm_store.get_items_for_session(session_id, include_types=include_types_list)

        result_items = []
        used_tokens = 0
        for item in items:
            if used_tokens + item.token_count <= budget:
                result_items.append({
                    "item_id": item.item_id,
                    "content_type": item.content_type,
                    "content": item.content,
                    "token_count": item.token_count,
                    "pinned": item.pinned,
                    "relevance_score": item.relevance_score,
                    "sequence_num": item.sequence_num
                })
                used_tokens += item.token_count

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
        if pinned is None and relevance_score is None:
            return json.dumps({"error": "No updates provided"})

        get_working_memory_store().update_item_flags(item_id, session_id, pinned, relevance_score)
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
        wm_store = get_working_memory_store()
        session_store = get_session_store()

        if preserve_pinned:
            count_before = wm_store.count_items(session_id)
            pinned_count = wm_store.count_items(session_id, pinned_only=True)
            count = count_before - pinned_count
            wm_store.delete_items(session_id, pinned_only=False)
            new_total = wm_store.sum_tokens(session_id)
        else:
            count = wm_store.count_items(session_id)
            wm_store.delete_items(session_id)
            new_total = 0

        session_store.update_total_tokens(session_id, new_total)

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
    wm_store = get_working_memory_store()
    session_store = get_session_store()

    candidates = wm_store.eviction_candidates(session_id)
    evicted = []
    freed_tokens = 0

    for item_id, token_count, _ in candidates:
        if freed_tokens >= tokens_needed:
            break
        wm_store.delete_item(item_id)
        evicted.append(item_id)
        freed_tokens += token_count

    if evicted:
        session_store.increment_total_tokens(session_id, -freed_tokens)

    return evicted
