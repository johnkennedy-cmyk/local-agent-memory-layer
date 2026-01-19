"""Stats and monitoring tools for FML dashboard."""

from typing import Optional
from src.db.client import db
from src.metrics import metrics


def register_stats_tools(mcp):
    """Register stats/monitoring tools with the MCP server."""

    @mcp.tool()
    def get_fml_stats(
        time_window_minutes: int = 60,
    ) -> dict:
        """
        Get FML server statistics and metrics.

        Args:
            time_window_minutes: Time window for recent metrics (default: 60)

        Returns:
            JSON with server stats, memory counts, and service metrics
        """
        # Get metrics from the collector
        service_stats = metrics.get_stats(time_window_minutes)

        # Get memory counts from database
        try:
            # Long-term memory count
            ltm_result = db.execute(
                "SELECT COUNT(*) FROM long_term_memories WHERE deleted_at IS NULL"
            )
            ltm_count = ltm_result[0][0] if ltm_result else 0

            # Working memory sessions
            sessions_result = db.execute(
                "SELECT COUNT(*) FROM session_contexts"
            )
            session_count = sessions_result[0][0] if sessions_result else 0

            # Working memory items
            wm_result = db.execute(
                "SELECT COUNT(*) FROM working_memory_items"
            )
            wm_items = wm_result[0][0] if wm_result else 0

            # Total tokens in working memory
            tokens_result = db.execute(
                "SELECT COALESCE(SUM(token_count), 0) FROM working_memory_items"
            )
            wm_tokens = tokens_result[0][0] if tokens_result else 0

            # Memory access log count
            access_result = db.execute(
                "SELECT COUNT(*) FROM memory_access_log"
            )
            access_log_count = access_result[0][0] if access_result else 0

            # Memory by category
            category_result = db.execute("""
                SELECT memory_category, COUNT(*) as cnt
                FROM long_term_memories
                WHERE deleted_at IS NULL
                GROUP BY memory_category
            """)
            by_category = {row[0]: row[1] for row in category_result}

            # Top accessed memories
            top_accessed = db.execute("""
                SELECT memory_id, memory_category, access_count, importance
                FROM long_term_memories
                WHERE deleted_at IS NULL
                ORDER BY access_count DESC
                LIMIT 5
            """)

            memory_stats = {
                "long_term_memories": ltm_count,
                "active_sessions": session_count,
                "working_memory_items": wm_items,
                "working_memory_tokens": wm_tokens,
                "access_log_entries": access_log_count,
                "by_category": by_category,
                "top_accessed": [
                    {
                        "memory_id": row[0][:8] + "...",
                        "category": row[1],
                        "access_count": row[2],
                        "importance": row[3],
                    }
                    for row in top_accessed
                ],
            }
        except Exception as e:
            memory_stats = {"error": str(e)}

        return {
            **service_stats,
            "memory": memory_stats,
        }

    @mcp.tool()
    def get_recent_calls(
        service: str = "ollama",
        limit: int = 50,
    ) -> dict:
        """
        Get recent API calls for a service.

        Args:
            service: Service name ('ollama', 'firebolt', 'embedding')
            limit: Maximum number of calls to return (default: 50)

        Returns:
            JSON with recent calls and their metrics
        """
        calls = metrics.get_recent_calls(service, limit)
        return {
            "service": service,
            "call_count": len(calls),
            "calls": calls,
        }

    @mcp.tool()
    def get_memory_analytics(
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Get detailed memory analytics.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            JSON with memory distribution, temporal trends, and usage patterns
        """
        try:
            # Build user filter
            user_filter = ""
            params = ()
            if user_id:
                user_filter = "AND user_id = ?"
                params = (user_id,)

            # Memory by subtype
            subtype_result = db.execute(f"""
                SELECT memory_category, memory_subtype, COUNT(*) as cnt
                FROM long_term_memories
                WHERE deleted_at IS NULL {user_filter}
                GROUP BY memory_category, memory_subtype
                ORDER BY cnt DESC
            """, params)

            by_subtype = [
                {"category": row[0], "subtype": row[1], "count": row[2]}
                for row in subtype_result
            ]

            # Entity distribution
            # Note: Firebolt array handling varies, so we count memories with entities
            entity_result = db.execute(f"""
                SELECT COUNT(*)
                FROM long_term_memories
                WHERE deleted_at IS NULL
                AND entities IS NOT NULL
                {user_filter}
            """, params)
            memories_with_entities = entity_result[0][0] if entity_result else 0

            # Importance distribution
            importance_result = db.execute(f"""
                SELECT
                    CASE
                        WHEN importance >= 0.8 THEN 'critical'
                        WHEN importance >= 0.6 THEN 'high'
                        WHEN importance >= 0.4 THEN 'medium'
                        ELSE 'low'
                    END as priority,
                    COUNT(*) as cnt
                FROM long_term_memories
                WHERE deleted_at IS NULL {user_filter}
                GROUP BY priority
            """, params)

            by_importance = {row[0]: row[1] for row in importance_result}

            # Recent activity (last 7 days of memory creation)
            # Using TIMESTAMPNTZ for Firebolt
            recent_result = db.execute(f"""
                SELECT COUNT(*)
                FROM long_term_memories
                WHERE deleted_at IS NULL
                AND created_at >= CURRENT_TIMESTAMP() - INTERVAL '7 days'
                {user_filter}
            """, params)
            recent_memories = recent_result[0][0] if recent_result else 0

            return {
                "by_subtype": by_subtype,
                "memories_with_entities": memories_with_entities,
                "by_importance": by_importance,
                "memories_last_7_days": recent_memories,
                "user_filter": user_id or "all",
            }
        except Exception as e:
            return {"error": str(e)}
