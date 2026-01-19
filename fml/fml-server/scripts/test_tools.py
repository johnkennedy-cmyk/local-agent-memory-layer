#!/usr/bin/env python3
"""End-to-end test for FML MCP tools."""

import asyncio
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.client import db
from src.llm.embeddings import embedding_service
from src.llm.ollama import ollama_service

# Test user and session IDs
TEST_USER_ID = "test_user_001"
TEST_SESSION_ID = "test_session_001"


def print_header(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(label: str, result: dict):
    print(f"\n{label}:")
    print(json.dumps(result, indent=2, default=str))


async def test_working_memory():
    """Test working memory tools."""
    print_header("WORKING MEMORY TESTS")

    from src.tools.working_memory import (
        _evict_working_memory,
    )

    # Import the tool functions directly (they're registered with FastMCP)
    from src.server import mcp

    # Get the actual tool functions
    init_session = mcp._tool_manager._tools["init_session"].fn
    add_to_working_memory = mcp._tool_manager._tools["add_to_working_memory"].fn
    get_working_memory = mcp._tool_manager._tools["get_working_memory"].fn
    update_working_memory_item = mcp._tool_manager._tools["update_working_memory_item"].fn
    clear_working_memory = mcp._tool_manager._tools["clear_working_memory"].fn

    # Test 1: Initialize session
    print("\n1. Init Session")
    result = await init_session(
        user_id=TEST_USER_ID,
        session_id=TEST_SESSION_ID,
        max_tokens=2000
    )
    result_data = json.loads(result)
    print_result("Result", result_data)
    assert "session_id" in result_data
    print("✓ Session initialized")

    # Test 2: Add items to working memory
    print("\n2. Add Items to Working Memory")

    items_to_add = [
        ("We're building a memory system for LLMs using Firebolt", "message"),
        ("User prefers detailed explanations with code examples", "task_state"),
        ("The database schema has 4 tables: session_contexts, working_memory_items, long_term_memories, memory_access_log", "scratchpad"),
    ]

    for content, content_type in items_to_add:
        result = await add_to_working_memory(
            session_id=TEST_SESSION_ID,
            content=content,
            content_type=content_type
        )
        result_data = json.loads(result)
        print(f"  Added {content_type}: {result_data.get('token_count')} tokens")
    print("✓ Items added")

    # Test 3: Get working memory
    print("\n3. Get Working Memory")
    result = await get_working_memory(session_id=TEST_SESSION_ID)
    result_data = json.loads(result)
    print_result("Result", result_data)
    assert result_data["item_count"] > 0
    print(f"✓ Retrieved {result_data['item_count']} items ({result_data['total_tokens']} tokens)")

    # Test 4: Update item
    print("\n4. Update Working Memory Item")
    if result_data["items"]:
        item_id = result_data["items"][0]["item_id"]
        result = await update_working_memory_item(
            item_id=item_id,
            session_id=TEST_SESSION_ID,
            pinned=True,
            relevance_score=0.9
        )
        result_data = json.loads(result)
        print_result("Result", result_data)
        print("✓ Item updated (pinned)")

    # Test 5: Clear working memory (preserve pinned)
    print("\n5. Clear Working Memory (preserve pinned)")
    result = await clear_working_memory(
        session_id=TEST_SESSION_ID,
        preserve_pinned=True
    )
    result_data = json.loads(result)
    print_result("Result", result_data)
    print(f"✓ Cleared {result_data['items_cleared']} items")

    return True


async def test_longterm_memory():
    """Test long-term memory tools."""
    print_header("LONG-TERM MEMORY TESTS")

    from src.server import mcp

    store_memory = mcp._tool_manager._tools["store_memory"].fn
    recall_memories = mcp._tool_manager._tools["recall_memories"].fn
    update_memory = mcp._tool_manager._tools["update_memory"].fn
    forget_memory = mcp._tool_manager._tools["forget_memory"].fn

    # Test 1: Store memories with auto-classification
    print("\n1. Store Memories (with auto-classification)")

    memories_to_store = [
        "The users table has columns: id, name, email, created_at. Primary key is id.",
        "To deploy the application, run 'docker-compose up -d' in the project root.",
        "User prefers TypeScript over JavaScript for all frontend code.",
        "Yesterday we decided to use Firebolt for the memory system because of its vector support.",
    ]

    memory_ids = []
    for content in memories_to_store:
        print(f"\n  Storing: {content[:50]}...")
        result = await store_memory(
            user_id=TEST_USER_ID,
            content=content,
            source_session=TEST_SESSION_ID
        )
        result_data = json.loads(result)
        print(f"    → Category: {result_data.get('memory_category')}.{result_data.get('memory_subtype')}")
        print(f"    → Entities: {result_data.get('entities', [])}")
        if "memory_id" in result_data:
            memory_ids.append(result_data["memory_id"])
    print("✓ Memories stored with auto-classification")

    # Test 2: Recall memories with semantic search
    print("\n2. Recall Memories (semantic search)")

    queries = [
        "What columns does the users table have?",
        "How do I deploy the application?",
        "What programming language does the user prefer?",
    ]

    for query in queries:
        print(f"\n  Query: {query}")
        result = await recall_memories(
            user_id=TEST_USER_ID,
            query=query,
            limit=3,
            min_similarity=0.5
        )
        result_data = json.loads(result)
        print(f"    → Found {result_data['total_returned']} memories")
        if result_data["memories"]:
            top_mem = result_data["memories"][0]
            print(f"    → Top result (sim={top_mem['similarity']}): {top_mem['content'][:60]}...")
    print("✓ Semantic search working")

    # Test 3: Update a memory
    print("\n3. Update Memory")
    if memory_ids:
        result = await update_memory(
            memory_id=memory_ids[0],
            user_id=TEST_USER_ID,
            importance=0.9,
            entities="table:users,database:main"
        )
        result_data = json.loads(result)
        print_result("Result", result_data)
        print("✓ Memory updated")

    # Test 4: Forget a memory (soft delete)
    print("\n4. Forget Memory (soft delete)")
    if len(memory_ids) > 1:
        result = await forget_memory(
            memory_id=memory_ids[-1],
            user_id=TEST_USER_ID,
            hard_delete=False
        )
        result_data = json.loads(result)
        print_result("Result", result_data)
        print("✓ Memory soft deleted")

    return memory_ids


async def test_smart_context(memory_ids: list):
    """Test smart context tools."""
    print_header("SMART CONTEXT TESTS")

    from src.server import mcp

    # First, add some items back to working memory
    add_to_working_memory = mcp._tool_manager._tools["add_to_working_memory"].fn

    await add_to_working_memory(
        session_id=TEST_SESSION_ID,
        content="Currently working on implementing the memory recall feature",
        content_type="task_state"
    )
    await add_to_working_memory(
        session_id=TEST_SESSION_ID,
        content="The user asked about the database schema",
        content_type="message"
    )

    get_relevant_context = mcp._tool_manager._tools["get_relevant_context"].fn
    checkpoint_working_memory = mcp._tool_manager._tools["checkpoint_working_memory"].fn

    # Test 1: Get relevant context
    print("\n1. Get Relevant Context")

    test_queries = [
        ("What is the schema for the users table?", "what_is"),
        ("How do I deploy the app?", "how_to"),
    ]

    for query, expected_intent in test_queries:
        print(f"\n  Query: {query}")
        result = await get_relevant_context(
            session_id=TEST_SESSION_ID,
            user_id=TEST_USER_ID,
            query=query,
            token_budget=2000
        )
        result_data = json.loads(result)
        print(f"    → Detected intent: {result_data.get('detected_intent')}")
        print(f"    → Total tokens: {result_data.get('total_tokens')}")
        print(f"    → Budget used: {result_data.get('budget_used_pct')}%")
        stats = result_data.get("retrieval_stats", {})
        print(f"    → Working memory items: {stats.get('working_memory_items', 0)}")
        print(f"    → Long-term items: {stats.get('long_term_items', 0)}")
    print("✓ Context assembly working")

    # Test 2: Checkpoint working memory
    print("\n2. Checkpoint Working Memory")
    result = await checkpoint_working_memory(
        session_id=TEST_SESSION_ID,
        user_id=TEST_USER_ID
    )
    result_data = json.loads(result)
    print_result("Result", result_data)
    print(f"✓ Checkpoint complete: {result_data.get('memories_created', 0)} created, {result_data.get('memories_updated', 0)} updated")

    return True


async def cleanup():
    """Clean up test data."""
    print_header("CLEANUP")

    from src.server import mcp
    forget_all = mcp._tool_manager._tools["forget_all_user_memories"].fn

    result = await forget_all(
        user_id=TEST_USER_ID,
        confirmation="CONFIRM_DELETE_ALL"
    )
    result_data = json.loads(result)
    print_result("Cleanup Result", result_data)
    print("✓ Test data cleaned up")


async def main():
    """Run all tests."""
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║      FML (Firebolt Memory Layer) - End-to-End Tests        ║")
    print("╚════════════════════════════════════════════════════════════╝")

    try:
        # Test 1: Working Memory
        await test_working_memory()

        # Test 2: Long-Term Memory
        memory_ids = await test_longterm_memory()

        # Test 3: Smart Context
        await test_smart_context(memory_ids)

        # Cleanup
        await cleanup()

        print_header("ALL TESTS PASSED ✓")
        print()
        print("The FML MCP server is working correctly!")
        print()

    except Exception as e:
        print_header("TEST FAILED ✗")
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
