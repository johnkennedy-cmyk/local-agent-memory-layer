"""Long-term memory MCP tools."""

import json
import traceback
import uuid
from typing import List, Optional
from mcp.server.fastmcp import FastMCP

from src.db.client import db
from src.llm.embeddings import embedding_service
from src.llm.ollama import ollama_service
from src.memory.backend import get_memory_repository, get_vector_store
from src.memory.taxonomy import validate_subtype
from src.metrics import log_tool_error
from src.security import validate_content_for_storage, SecurityViolation


def register_longterm_memory_tools(mcp: FastMCP):
    """Register long-term memory tools with the MCP server."""

    @mcp.tool()
    async def store_memory(
        user_id: str,
        content: str,
        memory_category: Optional[str] = None,
        memory_subtype: Optional[str] = None,
        importance: float = 0.5,
        entities: Optional[str] = None,
        event_time: Optional[str] = None,
        metadata: Optional[str] = None,
        source_session: Optional[str] = None
    ) -> str:
        """
        Store a memory in long-term storage with auto-classification.

        Args:
            user_id: User who owns this memory
            content: The content to store
            memory_category: Category ('episodic', 'semantic', 'procedural', 'preference')
                            If not provided, will be auto-classified using local LLM
            memory_subtype: Subtype within category (auto-classified if not provided)
            importance: Importance score 0.0 to 1.0 (default: 0.5)
            entities: Comma-separated entities (e.g., 'table:users,database:prod_db')
            event_time: ISO timestamp for when the event occurred (for episodic memories)
            metadata: JSON string with additional metadata
            source_session: Session ID that created this memory

        Returns:
            JSON with memory_id, classification, and extracted entities
        """
        try:
            return await _store_memory_impl(
                user_id, content, memory_category, memory_subtype,
                importance, entities, event_time, metadata, source_session
            )
        except Exception as e:
            log_tool_error(
                tool_name="store_memory",
                error_message=str(e),
                user_id=user_id,
                error_type=type(e).__name__,
                input_preview=content[:200] if content else None,
                stack_trace=traceback.format_exc()
            )
            raise  # Re-raise so MCP returns the error to user

    async def _store_memory_impl(
        user_id: str,
        content: str,
        memory_category: Optional[str],
        memory_subtype: Optional[str],
        importance: float,
        entities: Optional[str],
        event_time: Optional[str],
        metadata: Optional[str],
        source_session: Optional[str]
    ) -> str:
        """Internal implementation of store_memory."""
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
                "hint": "Sensitive data like API keys, passwords, and tokens should not be stored in memory. Store references or descriptions instead."
            })

        memory_id = str(uuid.uuid4())

        # Parse entities if provided as string
        entity_list = []
        if entities:
            entity_list = [e.strip() for e in entities.split(",") if e.strip()]

        # Auto-classify if category/subtype not provided
        if not memory_category or not memory_subtype:
            try:
                classification = ollama_service.classify_memory(content)
                memory_category = memory_category or classification.memory_category
                memory_subtype = memory_subtype or classification.memory_subtype

                # Use LLM-suggested importance if default
                if importance == 0.5:
                    importance = classification.importance

                # Use LLM-extracted entities if none provided
                if not entity_list:
                    entity_list = classification.entities
            except Exception as e:
                # Fallback to defaults if LLM fails
                memory_category = memory_category or "semantic"
                memory_subtype = memory_subtype or "domain"

        # Validate taxonomy
        if not validate_subtype(memory_category, memory_subtype):
            return json.dumps({
                "error": f"Invalid subtype '{memory_subtype}' for category '{memory_category}'"
            })

        # Extract additional entities if list is still empty
        if not entity_list:
            try:
                entity_list = ollama_service.extract_entities(content)
            except Exception:
                entity_list = []

        # Generate summary for long content (> 50 tokens) using OpenAI
        summary = None
        content_tokens = embedding_service.count_tokens(content)
        if content_tokens > 50:
            try:
                summary = ollama_service.summarize(content, max_words=50)
            except Exception:
                summary = None

        # Generate hypothetical questions for better semantic search using OpenAI
        hypothetical_questions = []
        try:
            hypothetical_questions = ollama_service.generate_hypothetical_questions(content)
        except Exception:
            hypothetical_questions = []

        # Create augmented text for embedding (content + questions for better retrieval)
        if hypothetical_questions:
            augmented_text = content + "\n\nQuestions this answers: " + " ".join(hypothetical_questions)
        else:
            augmented_text = content

        # Generate embedding from augmented text
        embedding = embedding_service.generate(augmented_text)

        # Check for similar existing memories to avoid duplicates
        similar = await _find_similar_memories(user_id, embedding, threshold=0.95)
        repo = get_memory_repository()

        if similar:
            # Very similar memory exists - update it instead
            existing_id = similar[0]["memory_id"]
            repo.update(
                existing_id,
                user_id,
                {
                    "content": content,
                    "summary": summary,
                    "embedding": embedding,
                    "importance": importance,
                },
            )
            repo.increment_access_count(existing_id)

            return json.dumps({
                "memory_id": existing_id,
                "action": "updated_existing",
                "memory_category": memory_category,
                "memory_subtype": memory_subtype,
                "entities": entity_list,
                "summary": summary,
                "content_tokens": content_tokens,
                "similar_memory": similar[0]
            })

        # Insert new memory
        doc = {
            "memory_id": memory_id,
            "user_id": user_id,
            "memory_category": memory_category,
            "memory_subtype": memory_subtype,
            "content": content,
            "summary": summary,
            "embedding": embedding,
            "entities": entity_list,
            "importance": importance,
            "event_time": event_time,
            "metadata": metadata,
            "is_temporal": event_time is not None,
            "source_session": source_session,
            "source_type": "conversation",
        }
        repo.insert(doc)

        return json.dumps({
            "memory_id": memory_id,
            "action": "created_new",
            "memory_category": memory_category,
            "memory_subtype": memory_subtype,
            "entities": entity_list,
            "importance": importance,
            "summary": summary,
            "content_tokens": content_tokens,
            "hypothetical_questions": hypothetical_questions
        })

    @mcp.tool()
    async def recall_memories(
        user_id: str,
        query: str,
        memory_categories: Optional[str] = None,
        memory_subtypes: Optional[str] = None,
        entities: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.2,
        include_related: bool = False
    ) -> str:
        """
        Recall relevant memories using semantic search.

        Args:
            user_id: User whose memories to search
            query: Natural language query for semantic search
            memory_categories: Comma-separated categories to filter (e.g., 'episodic,semantic')
            memory_subtypes: Comma-separated subtypes to filter (e.g., 'decision,entity')
            entities: Comma-separated entities for exact matching (e.g., 'table:users')
            limit: Maximum number of memories to return (default: 10)
            min_similarity: Minimum similarity threshold (default: 0.2)
            include_related: Include related memories for each result (chunking). Default: False

        Returns:
            JSON with matching memories and retrieval statistics
        """
        # Generate query embedding
        query_embedding = embedding_service.generate(query)
        vector_store = get_vector_store()
        repo = get_memory_repository()
        filters = {"user_id": user_id}

        # Check if user has any memories (vector search fails on empty in some backends)
        if repo.count_for_user(user_id) == 0:
            return json.dumps({
                "memories": [],
                "total_returned": 0,
                "query_tokens": embedding_service.count_tokens(query),
                "retrieval_breakdown": {"by_category": {}, "by_subtype": {}, "entity_matches": 0}
            })

        # Use the vector store to perform similarity search
        top_k = limit * 3
        search_results = vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filters,
        )

        if not search_results:
            return json.dumps({
                "memories": [],
                "total_returned": 0,
                "query_tokens": embedding_service.count_tokens(query),
                "retrieval_breakdown": {"by_category": {}, "by_subtype": {}, "entity_matches": 0}
            })

        ids = [res.memory_id for res in search_results]
        rows = repo.get_many_by_ids(ids, user_id=user_id)

        # Filter by similarity threshold and entity matching
        entity_filter = []
        if entities:
            entity_filter = [e.strip() for e in entities.split(",")]

        # Map similarity scores from search_results by memory_id
        similarity_by_id = {res.memory_id: res.score for res in search_results}

        memories = []
        for row in rows:
            mid = row["memory_id"]
            similarity = similarity_by_id.get(mid, 0.0)

            if similarity < min_similarity:
                continue

            memory_entities = row.get("entities") or []

            # Entity boost: increase effective similarity for entity matches
            entity_boost = 1.0
            if entity_filter and memory_entities:
                matches = len(set(entity_filter) & set(memory_entities))
                if matches > 0:
                    entity_boost = 1.0 + (0.2 * matches)

            effective_similarity = min(1.0, similarity * entity_boost)

            memories.append({
                "memory_id": mid,
                "content": row["content"],
                "summary": row.get("summary"),
                "memory_category": row["memory_category"],
                "memory_subtype": row["memory_subtype"],
                "entities": memory_entities,
                "importance": row.get("importance"),
                "access_count": row.get("access_count"),
                "created_at": str(row["created_at"]) if row.get("created_at") else None,
                "metadata": row.get("metadata"),
                "similarity": round(similarity, 4),
                "effective_similarity": round(effective_similarity, 4)
            })

            if len(memories) >= limit:
                break

        # Sort by effective similarity
        memories.sort(key=lambda x: x["effective_similarity"], reverse=True)

        # Update access counts for returned memories
        if memories:
            for mem in memories:
                repo.increment_access_count(mem["memory_id"])

        # Build retrieval breakdown
        breakdown = {
            "by_category": {},
            "by_subtype": {},
            "entity_matches": 0
        }

        for mem in memories:
            cat = mem["memory_category"]
            sub = mem["memory_subtype"]
            breakdown["by_category"][cat] = breakdown["by_category"].get(cat, 0) + 1
            breakdown["by_subtype"][sub] = breakdown["by_subtype"].get(sub, 0) + 1
            if entity_filter and mem["entities"]:
                if set(entity_filter) & set(mem["entities"]):
                    breakdown["entity_matches"] += 1

        # Include related memories if requested (chunking)
        if include_related and memories:
            seen_ids = {m["memory_id"] for m in memories}
            for mem in memories:
                rel_rows = db.execute(
                    "SELECT r.target_id, r.relationship, r.strength FROM memory_relationships r WHERE r.source_id = ? AND r.user_id = ? ORDER BY r.strength DESC LIMIT 3",
                    (mem["memory_id"], user_id),
                )
                if not rel_rows:
                    mem["related_memories"] = []
                    continue
                target_ids = [row[0] for row in rel_rows]
                target_docs = {m["memory_id"]: m for m in repo.get_many_by_ids(target_ids, user_id=user_id)}
                related_memories = []
                for row in rel_rows:
                    if row[0] not in seen_ids:
                        t = target_docs.get(row[0])
                        if not t:
                            continue
                        related_memories.append({
                            "memory_id": row[0],
                            "relationship": row[1],
                            "strength": row[2],
                            "content": t.get("content"),
                            "memory_category": t.get("memory_category"),
                            "memory_subtype": t.get("memory_subtype"),
                        })
                        seen_ids.add(row[0])
                mem["related_memories"] = related_memories
            
            breakdown["related_memories_included"] = sum(
                len(m.get("related_memories", [])) for m in memories
            )

        return json.dumps({
            "memories": memories,
            "total_returned": len(memories),
            "query_tokens": embedding_service.count_tokens(query),
            "retrieval_breakdown": breakdown
        })

    @mcp.tool()
    async def update_memory(
        memory_id: str,
        user_id: str,
        content: Optional[str] = None,
        importance: Optional[float] = None,
        entities: Optional[str] = None,
        metadata: Optional[str] = None
    ) -> str:
        """
        Update an existing memory.

        Args:
            memory_id: The memory to update
            user_id: User who owns the memory (for authorization)
            content: New content (will regenerate embedding if changed)
            importance: New importance score
            entities: New comma-separated entities
            metadata: New metadata JSON string

        Returns:
            JSON with success status
        """
        # Verify ownership
        repo = get_memory_repository()
        existing = repo.get_by_id(memory_id, user_id=user_id)

        if not existing:
            return json.dumps({"error": f"Memory not found: {memory_id}"})

        if existing.get("user_id") != user_id:
            return json.dumps({"error": "Unauthorized: memory belongs to different user"})

        fields = {}
        re_embedded = False

        if content is not None:
            # Security check: validate new content before updating
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
                    "hint": "Sensitive data like API keys, passwords, and tokens should not be stored in memory."
                })

            fields["content"] = content
            embedding = embedding_service.generate(content)
            fields["embedding"] = embedding
            re_embedded = True

        if importance is not None:
            fields["importance"] = importance

        if entities is not None:
            fields["entities"] = [e.strip() for e in entities.split(",") if e.strip()]

        if metadata is not None:
            fields["metadata"] = metadata

        if not fields:
            return json.dumps({"error": "No updates provided"})

        repo.update(memory_id, user_id, fields)

        return json.dumps({
            "success": True,
            "memory_id": memory_id,
            "re_embedded": re_embedded
        })

    @mcp.tool()
    async def forget_memory(
        memory_id: str,
        user_id: str,
        hard_delete: bool = False
    ) -> str:
        """
        Delete a memory (soft delete by default for GDPR compliance).

        Args:
            memory_id: The memory to delete
            user_id: User who owns the memory (for authorization)
            hard_delete: If True, permanently delete. If False, soft delete.

        Returns:
            JSON with success status
        """
        # Verify ownership
        repo = get_memory_repository()
        existing = repo.get_by_id(memory_id, include_deleted=True)

        if not existing:
            return json.dumps({"error": f"Memory not found: {memory_id}"})

        if existing.get("user_id") != user_id:
            return json.dumps({"error": "Unauthorized: memory belongs to different user"})

        if hard_delete:
            repo.hard_delete(memory_id, user_id)
        else:
            repo.soft_delete(memory_id, user_id)

        return json.dumps({
            "success": True,
            "memory_id": memory_id,
            "hard_deleted": hard_delete
        })

    @mcp.tool()
    async def forget_all_user_memories(
        user_id: str,
        confirmation: str
    ) -> str:
        """
        Delete all memories for a user (GDPR right to be forgotten).

        Args:
            user_id: User whose memories to delete
            confirmation: Must be "CONFIRM_DELETE_ALL" to proceed

        Returns:
            JSON with number of memories deleted
        """
        if confirmation != "CONFIRM_DELETE_ALL":
            return json.dumps({
                "error": "Confirmation required. Set confirmation to 'CONFIRM_DELETE_ALL'"
            })

        # Count memories and sessions
        repo = get_memory_repository()
        memory_count = repo.count_for_user(user_id, include_deleted=True)

        session_result = db.execute(
            "SELECT COUNT(*) FROM session_contexts WHERE user_id = ?",
            (user_id,)
        )
        session_count = session_result[0][0] if session_result else 0

        # Delete all user data (relationships and other tables in Firebolt; long-term memory via repo)
        db.execute("DELETE FROM memory_access_log WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM memory_relationships WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM working_memory_items WHERE user_id = ?", (user_id,))
        repo.delete_all_for_user(user_id)
        db.execute("DELETE FROM session_contexts WHERE user_id = ?", (user_id,))

        return json.dumps({
            "success": True,
            "memories_deleted": memory_count,
            "sessions_deleted": session_count,
            "user_id": user_id
        })

    # =========================================================================
    # MEMORY RELATIONSHIP TOOLS (Chunking)
    # =========================================================================

    @mcp.tool()
    async def link_memories(
        source_id: str,
        target_id: str,
        user_id: str,
        relationship: str = "related_to",
        strength: float = 1.0,
        context: Optional[str] = None,
        bidirectional: bool = True
    ) -> str:
        """
        Create a relationship between two memories (chunking).

        Supports the cognitive "Chunking" principle - grouping related items together
        for better recall. When one memory is retrieved, related memories can be
        pulled in for richer context.

        Args:
            source_id: The memory creating the relationship
            target_id: The memory being linked to
            user_id: User who owns both memories (for authorization)
            relationship: Type of relationship:
                - 'related_to': General association (default)
                - 'part_of': Target is a component/chunk of source
                - 'depends_on': Source requires target for context
                - 'contradicts': Memories have conflicting information
                - 'updates': Source is an update/correction of target
            strength: Relationship strength 0.0-1.0 (default: 1.0)
            context: Optional explanation of why these are related
            bidirectional: Create reverse link too (default: True)

        Returns:
            JSON with relationship details
        """
        # Verify both memories exist and belong to user
        repo = get_memory_repository()
        docs = repo.get_many_by_ids([source_id, target_id], user_id=user_id)
        source_doc = next((d for d in docs if d["memory_id"] == source_id), None)
        target_doc = next((d for d in docs if d["memory_id"] == target_id), None)
        if not source_doc:
            return json.dumps({"error": f"Source memory not found: {source_id}"})
        if not target_doc:
            return json.dumps({"error": f"Target memory not found: {target_id}"})

        # Validate relationship type
        valid_relationships = ["related_to", "part_of", "depends_on", "contradicts", "updates"]
        if relationship not in valid_relationships:
            return json.dumps({
                "error": f"Invalid relationship type: {relationship}",
                "valid_types": valid_relationships
            })

        # Check if relationship already exists
        existing = db.execute("""
            SELECT relationship_id FROM memory_relationships
            WHERE source_id = ? AND target_id = ? AND user_id = ?
        """, (source_id, target_id, user_id))

        if existing:
            # Update existing relationship
            db.execute("""
                UPDATE memory_relationships
                SET relationship = ?, strength = ?, context = ?
                WHERE source_id = ? AND target_id = ? AND user_id = ?
            """, (relationship, strength, context, source_id, target_id, user_id))
            action = "updated"
        else:
            # Create new relationship
            rel_id = str(uuid.uuid4())
            db.execute("""
                INSERT INTO memory_relationships (
                    relationship_id, source_id, target_id, user_id,
                    relationship, strength, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (rel_id, source_id, target_id, user_id, relationship, strength, context))
            action = "created"

        # Create bidirectional link if requested
        if bidirectional and relationship in ["related_to", "contradicts"]:
            reverse_existing = db.execute("""
                SELECT relationship_id FROM memory_relationships
                WHERE source_id = ? AND target_id = ? AND user_id = ?
            """, (target_id, source_id, user_id))

            if not reverse_existing:
                rev_id = str(uuid.uuid4())
                db.execute("""
                    INSERT INTO memory_relationships (
                        relationship_id, source_id, target_id, user_id,
                        relationship, strength, context
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (rev_id, target_id, source_id, user_id, relationship, strength, context))

        return json.dumps({
            "success": True,
            "action": action,
            "source": {
                "id": source_id,
                "content_preview": source[0][1][:80] + "..." if len(source[0][1]) > 80 else source[0][1]
            },
            "target": {
                "id": target_id,
                "content_preview": target[0][1][:80] + "..." if len(target[0][1]) > 80 else target[0][1]
            },
            "relationship": relationship,
            "strength": strength,
            "bidirectional": bidirectional and relationship in ["related_to", "contradicts"]
        })

    @mcp.tool()
    async def unlink_memories(
        source_id: str,
        target_id: str,
        user_id: str,
        bidirectional: bool = True
    ) -> str:
        """
        Remove a relationship between two memories.

        Args:
            source_id: The source memory of the relationship
            target_id: The target memory of the relationship
            user_id: User who owns the memories (for authorization)
            bidirectional: Also remove the reverse link (default: True)

        Returns:
            JSON with success status
        """
        # Delete the relationship
        db.execute("""
            DELETE FROM memory_relationships
            WHERE source_id = ? AND target_id = ? AND user_id = ?
        """, (source_id, target_id, user_id))

        if bidirectional:
            db.execute("""
                DELETE FROM memory_relationships
                WHERE source_id = ? AND target_id = ? AND user_id = ?
            """, (target_id, source_id, user_id))

        return json.dumps({
            "success": True,
            "unlinked": {
                "source_id": source_id,
                "target_id": target_id
            },
            "bidirectional": bidirectional
        })

    @mcp.tool()
    async def get_related_memories(
        memory_id: str,
        user_id: str,
        relationship_types: Optional[str] = None,
        include_reverse: bool = True,
        limit: int = 10
    ) -> str:
        """
        Get all memories related to a given memory.

        Retrieves the "chunk" of related memories for richer context during recall.
        This supports the cognitive Chunking principle.

        Args:
            memory_id: The memory to find relations for
            user_id: User who owns the memory (for authorization)
            relationship_types: Comma-separated relationship types to filter
                               (e.g., 'related_to,part_of'). None = all types.
            include_reverse: Include memories that link TO this memory (default: True)
            limit: Maximum related memories to return (default: 10)

        Returns:
            JSON with related memories and relationship details
        """
        # Verify memory exists
        repo = get_memory_repository()
        memory_docs = repo.get_many_by_ids([memory_id], user_id=user_id)
        if not memory_docs:
            return json.dumps({"error": f"Memory not found: {memory_id}"})
        memory_doc = memory_docs[0]

        # Build query for outgoing relationships
        conditions = ["r.source_id = ?", "r.user_id = ?"]
        params: List = [memory_id, user_id]

        if relationship_types:
            types = [t.strip() for t in relationship_types.split(",")]
            placeholders = ",".join(["?" for _ in types])
            conditions.append(f"r.relationship IN ({placeholders})")
            params.extend(types)

        where_clause = " AND ".join(conditions)

        # Get outgoing relationships (this memory -> others); memory content from repo
        outgoing = db.execute(
            f"SELECT r.target_id, r.relationship, r.strength, r.context FROM memory_relationships r WHERE {where_clause} ORDER BY r.strength DESC LIMIT ?",
            (*params, limit),
        )
        related = []
        if outgoing:
            out_ids = [row[0] for row in outgoing]
            out_mems = {m["memory_id"]: m for m in repo.get_many_by_ids(out_ids, user_id=user_id)}
            for row in outgoing:
                m = out_mems.get(row[0])
                if not m:
                    continue
                related.append({
                    "memory_id": row[0],
                    "relationship": row[1],
                    "direction": "outgoing",
                    "strength": row[2],
                    "context": row[3],
                    "content": m.get("content"),
                    "memory_category": m.get("memory_category"),
                    "memory_subtype": m.get("memory_subtype"),
                    "importance": m.get("importance"),
                })

        # Get incoming relationships (others -> this memory)
        if include_reverse:
            conditions[0] = "r.target_id = ?"
            params[0] = memory_id
            where_clause = " AND ".join(conditions)

            incoming = db.execute(
                f"SELECT r.source_id, r.relationship, r.strength, r.context FROM memory_relationships r WHERE {where_clause} ORDER BY r.strength DESC LIMIT ?",
                (*params, limit),
            )
            if incoming:
                in_ids = [row[0] for row in incoming]
                in_mems = {m["memory_id"]: m for m in repo.get_many_by_ids(in_ids, user_id=user_id)}
                for row in incoming:
                    if any(r["memory_id"] == row[0] for r in related):
                        continue
                    m = in_mems.get(row[0])
                    if not m:
                        continue
                    related.append({
                        "memory_id": row[0],
                        "relationship": row[1],
                        "direction": "incoming",
                        "strength": row[2],
                        "context": row[3],
                        "content": m.get("content"),
                        "memory_category": m.get("memory_category"),
                        "memory_subtype": m.get("memory_subtype"),
                        "importance": m.get("importance"),
                    })

        # Sort by strength and limit
        related.sort(key=lambda x: x["strength"], reverse=True)
        related = related[:limit]

        content = memory_doc.get("content") or ""
        return json.dumps({
            "memory_id": memory_id,
            "memory_content": content[:100] + "..." if len(content) > 100 else content,
            "memory_category": memory_doc.get("memory_category"),
            "related_count": len(related),
            "related_memories": related
        })

    @mcp.tool()
    async def auto_link_similar(
        memory_id: str,
        user_id: str,
        similarity_threshold: float = 0.75,
        max_links: int = 5
    ) -> str:
        """
        Automatically link a memory to similar memories.

        Uses vector similarity to find related memories and creates
        'related_to' relationships automatically. Useful for building
        memory chunks without manual curation.

        Args:
            memory_id: The memory to find similar memories for
            user_id: User who owns the memory
            similarity_threshold: Minimum similarity to create link (default: 0.75)
            max_links: Maximum number of links to create (default: 5)

        Returns:
            JSON with created links
        """
        # Get the memory and its content for re-embedding
        repo = get_memory_repository()
        vector_store = get_vector_store()
        memory_docs = repo.get_many_by_ids([memory_id], user_id=user_id)
        if not memory_docs:
            return json.dumps({"error": f"Memory not found: {memory_id}"})
        content = memory_docs[0]["content"]
        category = memory_docs[0]["memory_category"]

        embedding = embedding_service.generate(content)
        # Vector search for similar memories; filter by category in post-filter
        search_results = vector_store.search(
            query_embedding=embedding,
            top_k=max_links * 2,
            filters={"user_id": user_id},
        )
        # Get full docs to filter by category and get content
        similar_ids = [r.memory_id for r in search_results if r.memory_id != memory_id]
        similar_docs = repo.get_many_by_ids(similar_ids, user_id=user_id)
        similar_by_id = {m["memory_id"]: m for m in similar_docs}
        score_by_id = {r.memory_id: r.score for r in search_results}

        # Create links for memories above threshold (same category, score >= threshold)
        links_created = []
        for sim_id in similar_ids:
            if len(links_created) >= max_links:
                break
            m = similar_by_id.get(sim_id)
            if not m or m.get("memory_category") != category:
                continue
            similarity = score_by_id.get(sim_id) or 0.0
            if similarity < similarity_threshold:
                continue

            # Check if link already exists
            existing = db.execute("""
                SELECT 1 FROM memory_relationships
                WHERE source_id = ? AND target_id = ? AND user_id = ?
            """, (memory_id, sim_id, user_id))

            if not existing:
                sim_content = m.get("content") or ""
                rel_id = str(uuid.uuid4())
                db.execute("""
                    INSERT INTO memory_relationships (
                        relationship_id, source_id, target_id, user_id,
                        relationship, strength, context
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    rel_id, memory_id, sim_id, user_id,
                    "related_to", round(similarity, 4),
                    f"Auto-linked by similarity ({round(similarity, 2)})"
                ))

                # Bidirectional
                rev_id = str(uuid.uuid4())
                db.execute("""
                    INSERT INTO memory_relationships (
                        relationship_id, source_id, target_id, user_id,
                        relationship, strength, context
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    rev_id, sim_id, memory_id, user_id,
                    "related_to", round(similarity, 4),
                    f"Auto-linked by similarity ({round(similarity, 2)})"
                ))

                links_created.append({
                    "target_id": sim_id,
                    "content_preview": sim_content[:80] + "..." if len(sim_content) > 80 else sim_content,
                    "similarity": round(similarity, 4)
                })

        return json.dumps({
            "success": True,
            "memory_id": memory_id,
            "links_created": len(links_created),
            "links": links_created,
            "threshold_used": similarity_threshold
        })


def _format_embedding_literal(embedding: List[float]) -> str:
    """Format embedding as SQL literal for vector_search TVF (required for Firebolt 4.28)."""
    values = ", ".join(str(v) for v in embedding)
    return f"[{values}]::ARRAY(DOUBLE)"


async def _find_similar_memories(
    user_id: str,
    embedding: List[float],
    threshold: float = 0.95
) -> List[dict]:
    """Find memories with very high similarity (for deduplication). Uses configured vector store."""
    repo = get_memory_repository()
    vector_store = get_vector_store()
    if repo.count_for_user(user_id) == 0:
        return []

    search_results = vector_store.search(
        query_embedding=embedding,
        top_k=10,
        filters={"user_id": user_id},
    )
    if not search_results:
        return []

    ids = [r.memory_id for r in search_results]
    docs = repo.get_many_by_ids(ids, user_id=user_id)
    by_id = {m["memory_id"]: m for m in docs}
    similar = []
    for r in search_results:
        if r.score >= threshold:
            m = by_id.get(r.memory_id)
            content = (m.get("content") or "")[:100]
            if len(m.get("content") or "") > 100:
                content += "..."
            similar.append({
                "memory_id": r.memory_id,
                "content": content,
                "similarity": round(r.score, 4),
            })
        if len(similar) >= 3:
            break
    return similar
