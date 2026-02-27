#!/usr/bin/env python3
"""Query Firebolt for LAML sessions and memory summary (validates project/session storage)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import db
from src.config import config


def main():
    print("LAML Session & Storage Summary (Firebolt)")
    print("=" * 50)
    print(f"Database: {config.firebolt.database}")
    print(f"Vector backend: {getattr(config, 'vector_backend', 'firebolt')}")
    print()

    # Health check
    try:
        db.execute("SELECT 1")
    except Exception as e:
        print(f"Database connection failed: {e}")
        return 1

    # Sessions (these are the "projects" / chat sessions Cursor uses)
    try:
        sessions = db.execute("""
            SELECT session_id, user_id, org_id, total_tokens, max_tokens, created_at, last_activity
            FROM session_contexts
            ORDER BY last_activity DESC
        """)
    except Exception as e:
        print(f"Could not read session_contexts: {e}")
        return 1

    print(f"Sessions stored: {len(sessions)}")
    if not sessions:
        print("  (No sessions yet. Init a session from Cursor to create one.)")
        print()
    else:
        print()
        for i, row in enumerate(sessions[:20], 1):
            sid, uid, org, tokens, max_tok, created, last = row
            sid_short = (sid[:12] + "…") if sid and len(sid) > 12 else (sid or "")
            print(f"  {i}. user_id={uid}  session_id={sid_short}  tokens={tokens}/{max_tok}  last_activity={last}")
        if len(sessions) > 20:
            print(f"  ... and {len(sessions) - 20} more")
        print()

    # Working memory items count per session
    try:
        wm = db.execute("""
            SELECT session_id, COUNT(*), COALESCE(SUM(token_count), 0)
            FROM working_memory_items
            GROUP BY session_id
        """)
        total_items = sum(r[1] for r in wm)
        total_tokens_wm = sum(r[2] for r in wm)
        print(f"Working memory: {total_items} items across {len(wm)} session(s), {total_tokens_wm} tokens total")
        print()
    except Exception as e:
        print(f"Could not read working_memory_items: {e}")
        print()

    # Long-term memories (from configured backend; Firebolt when vector_backend=firebolt)
    try:
        if getattr(config, "vector_backend", "firebolt") == "firebolt":
            ltm = db.execute("SELECT COUNT(*) FROM long_term_memories WHERE deleted_at IS NULL")
            ltm_count = ltm[0][0] if ltm else 0
            by_cat = db.execute("""
                SELECT memory_category, COUNT(*) FROM long_term_memories WHERE deleted_at IS NULL GROUP BY memory_category
            """)
            print(f"Long-term memories: {ltm_count}")
            if by_cat:
                for cat, cnt in by_cat:
                    print(f"  - {cat}: {cnt}")
        else:
            from src.memory.backend import get_memory_repository
            repo = get_memory_repository()
            ltm_count = repo.count_total(include_deleted=False)
            print(f"Long-term memories (Elastic): {ltm_count}")
        print()
    except Exception as e:
        print(f"Could not read long_term_memories: {e}")
        print()

    print("Validation: Cursor projects/sessions are stored in Firebolt in session_contexts and working_memory_items.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
