# Firebolt Memory Layer (FML)
## Technical Specification v0.1

**Status:** Draft
**Last Updated:** January 8, 2026
**Authors:** [TBD]

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Cognitive Architecture Principles](#4-cognitive-architecture-principles)
5. [Technical Architecture](#5-technical-architecture)
6. [Data Model](#6-data-model)
7. [MCP Server Interface](#7-mcp-server-interface)
8. [Core Algorithms](#8-core-algorithms)
9. [Integration Patterns](#9-integration-patterns)
10. [Security & Privacy](#10-security--privacy)
11. [Performance Requirements](#11-performance-requirements)
12. [Open Questions](#12-open-questions)
13. [Appendix](#13-appendix)

---

## 1. Executive Summary

Firebolt Memory Layer (FML) is a memory management system for LLM-powered applications. It provides persistent, intelligent memory that eliminates the need for lossy conversation summarization by implementing a two-tier memory architecture inspired by human cognition:

- **Working Memory**: Fast, structured storage for active session context
- **Long-Term Memory**: Vector-enabled persistent storage for cross-session recall

FML exposes its capabilities via the Model Context Protocol (MCP), enabling integration with IDEs (Cursor, VS Code), chatbots, and custom AI applications.

**Value Proposition:**
- Eliminates "summarizing your conversation" latency and information loss
- Provides vendor-neutral memory infrastructure
- Leverages Firebolt's sub-second analytics and vector search at scale

---

## 2. Problem Statement

### 2.1 Current State

LLM applications face a fundamental constraint: **fixed context windows**. When conversations exceed this limit, applications must either:

1. **Truncate**: Drop older messages (loses context)
2. **Summarize**: Compress conversation history (slow, lossy, breaks user flow)
3. **Sliding Window**: Keep only recent N messages (loses important early context)

All approaches degrade user experience and reduce LLM effectiveness.

### 2.2 User Pain Points

| Pain Point | Impact |
|------------|--------|
| "Summarizing your conversation..." | 10-30 second delays; breaks flow |
| Lost context | LLM forgets user preferences, prior decisions, important details |
| No cross-session memory | Every conversation starts fresh |
| Redundant explanations | Users must re-explain context repeatedly |

### 2.3 Developer Pain Points

| Pain Point | Impact |
|------------|--------|
| Building custom memory systems | Significant engineering investment |
| Scaling memory infrastructure | Operational complexity |
| Balancing relevance vs. recency | Hard ML problem |
| Multi-tenant data isolation | Security/compliance burden |

---

## 3. Goals & Non-Goals

### 3.1 Goals

| ID | Goal | Success Metric |
|----|------|----------------|
| G1 | Eliminate summarization delays | Zero "summarizing" messages to users |
| G2 | Preserve important context | 95%+ of user-flagged important items recallable |
| G3 | Sub-second memory operations | p99 latency < 200ms for all MCP tools |
| G4 | Seamless MCP integration | Works with Cursor, Claude Desktop, custom apps |
| G5 | Horizontal scalability | Support 10K+ concurrent sessions without degradation |
| G6 | Multi-tenant isolation | Complete data separation between users/orgs |

### 3.2 Non-Goals (v1)

| ID | Non-Goal | Rationale |
|----|----------|-----------|
| NG1 | Embedding model hosting | Use external embedding APIs; avoid ML infra complexity |
| NG2 | LLM hosting | FML is memory layer only; LLM is client's responsibility |
| NG3 | Conversation UI | FML is infrastructure; UIs are built by integrators |
| NG4 | Real-time collaboration | Single-user sessions only in v1 |
| NG5 | On-premise deployment | Cloud-first; self-hosted comes later |

---

## 4. Cognitive Architecture Principles

Before diving into technical architecture, we establish the cognitive science principles that guide this design. FML is modeled on human memory systems, adapted for LLM use cases.

### 4.1 Human Memory Systems → FML Mapping

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HUMAN COGNITION                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PREFRONTAL CORTEX                    HIPPOCAMPUS + CORTEX                  │
│  (Working Memory)                     (Long-Term Memory)                    │
│                                                                             │
│  • Limited capacity (~7 items)        • Virtually unlimited                 │
│  • Fast access (immediate)            • Slower access (retrieval)           │
│  • Requires attention                 • Consolidated during rest            │
│  • Volatile (lost if distracted)      • Persistent (can last lifetime)      │
│                                                                             │
│        ↓ ↓ ↓                                  ↓ ↓ ↓                          │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                           FML SYSTEM                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CONTEXT WINDOW                       FIREBOLT STORAGE                      │
│  (Working Memory)                     (Long-Term Memory)                    │
│                                                                             │
│  • Token-limited (~8K-200K)           • Unlimited (scales horizontally)     │
│  • Instant access (in-context)        • Query latency (~50-200ms)           │
│  • Requires active management         • Automatic persistence               │
│  • Lost at session end                • Persists across sessions            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Cognitive Principles Applied

| Human Principle | Description | FML Implementation |
|-----------------|-------------|-------------------|
| **Levels of Processing** | Deeper processing → stronger memories | Memories with rich metadata (entities, reasoning, context) have higher retrieval priority |
| **Encoding Specificity** | Retrieval cues should match encoding context | Store retrieval context (query, session state) with memories; use for relevance boosting |
| **Spacing Effect** | Repeated exposure strengthens memory | `access_count` tracks retrieval frequency; frequently accessed memories get importance boost |
| **Forgetting Curve** | Memories decay over time without reinforcement | Time decay factor in relevance scoring; but never hard-delete (humans don't truly forget) |
| **Chunking** | Related items grouped together | Group related memories (all table fields together); `related_memories` field |
| **Context-Dependent Memory** | Recall is better in similar contexts | Session context stored; similar contexts boost retrieval |
| **Reconstruction** | Memory is reconstructed, not replayed | Allow memory updates; `supersedes` field for corrections |
| **Interference** | New info can interfere with old | Detect conflicting memories; lower confidence on older conflicting info |
| **Emotional Salience** | Emotionally significant = better remembered | `importance` field; explicit user emphasis; error contexts |
| **Prospective Memory** | Remembering to do future tasks | Task state tracking in working memory; scheduled triggers |

### 4.3 Query-Dependent Retrieval Profiles

Just as humans retrieve different types of memories depending on the question, FML adjusts retrieval strategy based on query intent:

```
QUERY TYPE          HUMAN ANALOGY                    FML RETRIEVAL PROFILE
─────────────────────────────────────────────────────────────────────────────

"How do I...?"      Reaching for procedural          procedural.workflow: HIGH
(how_to)            memory (motor cortex)            procedural.pattern: HIGH
                                                     semantic.project: MEDIUM
                                                     preference.style: MEDIUM

"What happened      Episodic recall                  episodic.decision: HIGH
when...?"           (hippocampus → cortex)           episodic.event: HIGH
(what_happened)                                      episodic.outcome: MEDIUM

"What is...?"       Semantic knowledge               semantic.entity: HIGH
(what_is)           retrieval (cortex)               semantic.project: HIGH
                                                     semantic.domain: MEDIUM

"Why isn't this     Problem-solving mode             procedural.debugging: HIGH
working?"           (prefrontal + memory)            episodic.outcome: HIGH
(debug)                                              semantic.environment: MEDIUM

"Remember that      Explicit storage request         Direct storage, no retrieval
X..."               (intentional encoding)           High importance flag
(store)
```

### 4.4 The "No Summarization" Principle

Traditional approaches compress the entire context window when it fills up:

```
TRADITIONAL APPROACH (Bad)
─────────────────────────────────────────────────────
│ Message 1    │ → │ Message 1    │ → │             │
│ Message 2    │   │ Message 2    │   │ "Summary of │
│ Message 3    │   │ Message 3    │   │  messages   │
│ Message 4    │   │ Message 4    │   │  1-7"       │
│ Message 5    │   │ Message 5    │   │             │
│ ...          │   │ ...          │   │ Message 8   │
│              │   │ Message 7    │   │ Message 9   │
│ [space]      │   │ Message 8    │   │ Message 10  │
─────────────────────────────────────────────────────
                   FULL!              SUMMARIZE 😓
                                      (slow, lossy)
```

FML approach: **selective eviction with long-term promotion**

```
FML APPROACH (Good)
─────────────────────────────────────────────────────
│ Message 1    │ → │ Message 1    │ → │ Retrieved:  │
│ Message 2    │   │ Message 2    │   │  Decision X │
│ Message 3    │   │ [evicted→LTM]│   │             │
│ Message 4    │   │ [evicted→LTM]│   │ Message 5   │
│ Message 5    │   │ Message 5    │   │ ...         │
│ ...          │   │ ...          │   │ Message 10  │
│              │   │ Message 7    │   │ Message 11  │
│ [space]      │   │ Message 8    │   │ [space]     │
─────────────────────────────────────────────────────
                   APPROACHING        EVICTED items
                   LIMIT              stored in LTM,
                                      retrieved when
                                      relevant ✓
```

Key differences:
1. **No user-visible delay** - eviction happens incrementally, not all at once
2. **No information loss** - evicted items go to long-term memory, not trash
3. **Selective retrieval** - only bring back what's relevant to current query
4. **Smarter context use** - context window has relevant info, not just recent info

---

## 5. Technical Architecture

### 5.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Client Applications                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐   │
│  │   Cursor    │  │Claude Desktop│ │  Custom App │  │ Chatbot UI    │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───────┬───────┘   │
└─────────┼────────────────┼────────────────┼─────────────────┼───────────┘
          │                │                │                 │
          └────────────────┴────────┬───────┴─────────────────┘
                                    │ MCP Protocol (stdio/SSE)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FML MCP Server                                  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Authentication Layer                        │   │
│  │                   (API Keys / OAuth / JWT)                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌───────────────────────┐      ┌───────────────────────────────────┐   │
│  │  Working Memory       │      │  Long-Term Memory Manager         │   │
│  │  Manager              │      │                                   │   │
│  │                       │      │  ┌─────────┐ ┌─────────┐ ┌─────┐  │   │
│  │  • Session state      │      │  │Episodic │ │Semantic │ │Proc.│  │   │
│  │  • Active context     │      │  │ Memory  │ │ Memory  │ │Mem. │  │   │
│  │  • Token budgeting    │      │  └─────────┘ └─────────┘ └─────┘  │   │
│  │  • Eviction policy    │      │                                   │   │
│  └───────────┬───────────┘      └─────────────────┬─────────────────┘   │
│              │                                    │                     │
│  ┌───────────┴────────────────────────────────────┴─────────────────┐   │
│  │                    Embedding Service                              │   │
│  │              (OpenAI / Cohere / Local Model)                      │   │
│  └───────────────────────────────────┬──────────────────────────────┘   │
│                                      │                                  │
│  ┌───────────────────────────────────┴──────────────────────────────┐   │
│  │                    Firebolt Client                                │   │
│  │                  (Connection pooling, query building)             │   │
│  └───────────────────────────────────┬──────────────────────────────┘   │
└──────────────────────────────────────┼──────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Firebolt                                      │
│                                                                         │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │   working_memory        │    │   long_term_memory                  │ │
│  │   (Structured Data)     │    │   (Vector + Structured)             │ │
│  │                         │    │                                     │ │
│  │   • session_contexts    │    │   • episodic_memories               │ │
│  │   • task_states         │    │   • semantic_memories               │ │
│  │   • scratchpad_items    │    │   • procedural_memories             │ │
│  │                         │    │   • memory_access_log               │ │
│  └─────────────────────────┘    └─────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **MCP Server** | Protocol handling, request routing, response formatting |
| **Auth Layer** | API key validation, tenant isolation, rate limiting |
| **Working Memory Manager** | Session lifecycle, token budgeting, eviction |
| **Long-Term Memory Manager** | Memory classification, storage, retrieval ranking |
| **Embedding Service** | Generate embeddings for semantic search |
| **Firebolt Client** | Query execution, connection management |

### 5.3 Data Flow: Memory Retrieval

```
User Query: "What did we decide about the authentication approach?"

1. Client sends query to LLM
2. LLM (or client) calls FML: recall_memories(query, types=['episodic', 'semantic'])
3. FML generates embedding for query
4. FML executes hybrid search:
   - Vector similarity on long_term_memory
   - Boost by recency, importance, access_count
   - Filter by user_id, memory_type
5. FML returns top-k relevant memories
6. Client injects memories into LLM context
7. LLM responds with full context awareness
```

### 5.4 Data Flow: Memory Storage

```
End of conversation turn:

1. Client calls FML: checkpoint_working_memory(session_id)
2. FML analyzes working memory for storage candidates:
   - New facts learned (→ semantic memory)
   - Events/decisions made (→ episodic memory)
   - User preferences expressed (→ procedural memory)
3. FML generates embeddings for new memories
4. FML stores to long_term_memory with metadata
5. FML prunes working memory to stay within token budget
6. Client continues with fresh context window space
```

---

## 6. Data Model

### 6.1 Working Memory Schema

```sql
-- Active session contexts
CREATE TABLE session_contexts (
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    org_id          TEXT,

    -- Context window management
    total_tokens    INT DEFAULT 0,
    max_tokens      INT DEFAULT 8000,

    -- Session metadata
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP,

    -- Session configuration
    config          JSONB,  -- {"model": "claude-3", "temperature": 0.7, ...}

    PRIMARY KEY (session_id)
);

-- Individual items in working memory
CREATE TABLE working_memory_items (
    item_id         TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,

    -- Content
    content_type    TEXT NOT NULL,  -- 'message', 'task_state', 'scratchpad', 'retrieved_memory'
    content         TEXT NOT NULL,
    token_count     INT NOT NULL,

    -- Relevance tracking
    relevance_score FLOAT DEFAULT 1.0,
    pinned          BOOLEAN DEFAULT FALSE,  -- User/system marked as important

    -- Ordering
    sequence_num    INT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (item_id)
);

CREATE INDEX idx_wmi_session ON working_memory_items(session_id, sequence_num);

-- Task state for complex multi-step operations
CREATE TABLE task_states (
    task_id         TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,

    -- Task definition
    task_type       TEXT NOT NULL,
    status          TEXT DEFAULT 'in_progress',  -- 'pending', 'in_progress', 'completed', 'failed'

    -- State data
    context         JSONB,      -- Task-specific context
    parameters      JSONB,      -- Input parameters
    intermediate    JSONB,      -- Intermediate results

    -- Timestamps
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (task_id)
);
```

### 6.2 Long-Term Memory Schema

```sql
-- Core long-term memory table with vector embeddings
CREATE TABLE long_term_memories (
    memory_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    org_id          TEXT,

    -- Memory classification (human-aligned taxonomy)
    memory_category TEXT NOT NULL,  -- 'episodic', 'semantic', 'procedural', 'preference'
    memory_subtype  TEXT NOT NULL,  -- See subtype enums per category

    -- Content
    content         TEXT NOT NULL,
    summary         TEXT,           -- Optional condensed version

    -- Vector embedding for semantic search (Firebolt uses ARRAY for vectors)
    -- Use VECTOR_COSINE_SIMILARITY() for retrieval
    embedding       ARRAY(REAL),    -- 1536 dimensions for text-embedding-3-small

    -- Named entities for precise retrieval
    entities        TEXT[],         -- ['database:prod_db', 'table:users', 'file:api.py']

    -- Metadata
    metadata        JSONB,          -- Flexible: {source, tags, reasoning, ...}

    -- Temporal context (for episodic memories)
    event_time      TIMESTAMP,      -- When the event/decision occurred (if applicable)
    is_temporal     BOOLEAN DEFAULT FALSE,  -- Is this time-sensitive info?

    -- Importance & access patterns
    importance      FLOAT DEFAULT 0.5,  -- 0.0 to 1.0
    access_count    INT DEFAULT 0,
    decay_factor    FLOAT DEFAULT 1.0,  -- For time-based relevance decay

    -- Relationships to other memories
    related_memories TEXT[],        -- IDs of connected memories (chunking)
    supersedes      TEXT,           -- ID of memory this one replaces (corrections)

    -- Source tracking
    source_session  TEXT,           -- Session that created this memory
    source_type     TEXT,           -- 'conversation', 'explicit', 'inferred', 'observed'
    confidence      FLOAT DEFAULT 1.0,  -- How confident are we in this memory?

    -- Timestamps
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Soft delete for GDPR compliance
    deleted_at      TIMESTAMP,

    PRIMARY KEY (memory_id)
);

-- Subtype validation constraints
ALTER TABLE long_term_memories ADD CONSTRAINT valid_episodic_subtype
    CHECK (memory_category != 'episodic' OR memory_subtype IN ('event', 'decision', 'conversation', 'outcome'));

ALTER TABLE long_term_memories ADD CONSTRAINT valid_semantic_subtype
    CHECK (memory_category != 'semantic' OR memory_subtype IN ('user', 'project', 'environment', 'domain', 'entity'));

ALTER TABLE long_term_memories ADD CONSTRAINT valid_procedural_subtype
    CHECK (memory_category != 'procedural' OR memory_subtype IN ('workflow', 'pattern', 'tool_usage', 'debugging'));

ALTER TABLE long_term_memories ADD CONSTRAINT valid_preference_subtype
    CHECK (memory_category != 'preference' OR memory_subtype IN ('communication', 'style', 'tools', 'boundaries'));

-- Indexes for common query patterns
CREATE INDEX idx_ltm_user_type ON long_term_memories(user_id, memory_type)
    WHERE deleted_at IS NULL;
-- Note: Firebolt's columnar storage handles vector operations efficiently without special index
CREATE INDEX idx_ltm_importance ON long_term_memories(user_id, importance DESC);

-- Memory access log for analytics and relevance tuning
CREATE TABLE memory_access_log (
    access_id       TEXT NOT NULL,
    memory_id       TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,

    -- Access context
    query_text      TEXT,
    query_embedding VECTOR(1536),
    similarity_score FLOAT,

    -- Feedback (for relevance tuning)
    was_useful      BOOLEAN,        -- Explicit user feedback
    was_used        BOOLEAN,        -- Did LLM reference this memory?

    accessed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (access_id)
);
```

### 6.3 Memory Taxonomy (Human-Aligned)

The memory taxonomy is designed to mirror how human memory actually works, adapted for LLM assistant use cases.

#### 5.3.1 Memory Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WORKING MEMORY                                    │
│                    (Active Context Window - Ephemeral)                      │
│                                                                             │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────────┐   │
│  │ Conversation    │ │ Task State      │ │ Active Context              │   │
│  │ Buffer          │ │ Scratchpad      │ │ (files, code, environment)  │   │
│  │                 │ │                 │ │                             │   │
│  │ Recent messages │ │ Current goals   │ │ Open files                  │   │
│  │ Active thread   │ │ Intermediate    │ │ Recent edits                │   │
│  │                 │ │ results         │ │ Error context               │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌───────────────────────────────────┐ ┌───────────────────────────────────────┐
│      DECLARATIVE MEMORY           │ │       NON-DECLARATIVE MEMORY          │
│      (Explicit Recall)            │ │       (Implicit Influence)            │
│                                   │ │                                       │
│  ┌─────────────────────────────┐  │ │  ┌─────────────────────────────────┐  │
│  │     EPISODIC MEMORY         │  │ │  │     PROCEDURAL MEMORY           │  │
│  │     (What Happened)         │  │ │  │     (How To Do Things)          │  │
│  │                             │  │ │  │                                 │  │
│  │  • Events & Decisions       │  │ │  │  • Task Workflows               │  │
│  │  • Conversation History     │  │ │  │  • Code Patterns                │  │
│  │  • Outcomes & Results       │  │ │  │  • Tool Usage Sequences         │  │
│  │  • Temporal Context         │  │ │  │  • Debugging Approaches         │  │
│  └─────────────────────────────┘  │ │  └─────────────────────────────────┘  │
│                                   │ │                                       │
│  ┌─────────────────────────────┐  │ │  ┌─────────────────────────────────┐  │
│  │     SEMANTIC MEMORY         │  │ │  │     PREFERENCE MEMORY           │  │
│  │     (Facts & Knowledge)     │  │ │  │     (Learned Behaviors)         │  │
│  │                             │  │ │  │                                 │  │
│  │  ┌───────────────────────┐  │  │ │  │  • Communication Style          │  │
│  │  │ User Knowledge        │  │  │ │  │  • Detail Level Preferences     │  │
│  │  │ • Identity & Role     │  │  │ │  │  • Tool Preferences             │  │
│  │  │ • Skills & Expertise  │  │  │ │  │  • Response Format Prefs        │  │
│  │  │ • Goals & Priorities  │  │  │ │  │  • Feedback Patterns            │  │
│  │  └───────────────────────┘  │  │ │  └─────────────────────────────────┘  │
│  │                             │  │ │                                       │
│  │  ┌───────────────────────┐  │  │ └───────────────────────────────────────┘
│  │  │ Project Knowledge     │  │  │
│  │  │ • Repo Structure      │  │  │
│  │  │ • Tech Stack          │  │  │
│  │  │ • Conventions         │  │  │
│  │  │ • Database Schemas    │  │  │
│  │  │ • API Endpoints       │  │  │
│  │  └───────────────────────┘  │  │
│  │                             │  │
│  │  ┌───────────────────────┐  │  │
│  │  │ Domain Knowledge      │  │  │
│  │  │ • Technical Concepts  │  │  │
│  │  │ • Industry Context    │  │  │
│  │  │ • External Systems    │  │  │
│  │  └───────────────────────┘  │  │
│  └─────────────────────────────┘  │
└───────────────────────────────────┘
```

#### 5.3.2 Memory Type Definitions

##### EPISODIC MEMORY — "What Happened"
*Human analogy: Remembering your wedding day, a conversation you had yesterday*

| Subtype | Description | Examples | Storage Triggers |
|---------|-------------|----------|------------------|
| **Events** | Discrete occurrences with temporal context | "Deployed v2.3 to production on Jan 5" | Task completion, deployments, milestones |
| **Decisions** | Choices made with reasoning | "Chose PostgreSQL over MySQL because of JSONB support" | Explicit decisions, trade-off discussions |
| **Conversations** | Significant exchanges | "Discussed auth architecture with user on Jan 3" | End of substantive conversations |
| **Outcomes** | Results of actions | "Migration failed due to foreign key constraint" | Task success/failure, error resolution |

```sql
-- Episodic memory subtypes
memory_subtype ENUM('event', 'decision', 'conversation', 'outcome')
```

##### SEMANTIC MEMORY — "Facts & Knowledge"
*Human analogy: Knowing Paris is in France, knowing how TCP/IP works*

| Subtype | Description | Examples | Storage Triggers |
|---------|-------------|----------|------------------|
| **User Knowledge** | Facts about the user | "User is a senior backend engineer", "User's name is Sarah" | User shares info, profile updates |
| **Project Knowledge** | Facts about current project/repo | "Database is named `prod_analytics`", "Uses FastAPI with SQLAlchemy" | Codebase exploration, user corrections |
| **Environment Knowledge** | Technical environment details | "Running Python 3.11 on macOS", "CI uses GitHub Actions" | Environment detection, user mentions |
| **Domain Knowledge** | General technical/domain facts | "Firebolt uses columnar storage", "OAuth2 requires redirect URIs" | Learning from explanations, documentation |
| **Entity Knowledge** | Specific named entities | "Table `users` has fields: id, email, created_at", "API endpoint is /api/v2/users" | Schema discovery, API exploration |

```sql
-- Semantic memory subtypes
memory_subtype ENUM('user', 'project', 'environment', 'domain', 'entity')
```

##### PROCEDURAL MEMORY — "How To Do Things"
*Human analogy: Knowing how to ride a bike, touch typing*

| Subtype | Description | Examples | Storage Triggers |
|---------|-------------|----------|------------------|
| **Workflows** | Multi-step processes | "To deploy: run tests → build → push → deploy" | Repeated successful sequences |
| **Patterns** | Code/solution patterns | "Error handling in this codebase uses Result type" | Pattern recognition across tasks |
| **Tool Usage** | How to use specific tools | "Use `pnpm` not `npm` in this project" | Tool corrections, successful tool use |
| **Debugging** | Problem-solving approaches | "When API times out, check Redis connection first" | Successful debugging sessions |

```sql
-- Procedural memory subtypes
memory_subtype ENUM('workflow', 'pattern', 'tool_usage', 'debugging')
```

##### PREFERENCE MEMORY — "Learned Behaviors"
*Human analogy: Knowing your friend likes tea not coffee, learned habits*

| Subtype | Description | Examples | Storage Triggers |
|---------|-------------|----------|------------------|
| **Communication** | How user likes to interact | "User prefers concise answers", "Likes code examples first" | Explicit feedback, response patterns |
| **Style** | Code/work style preferences | "Prefers functional style over OOP", "Uses 2-space indentation" | Code corrections, explicit preferences |
| **Tools** | Tool/technology preferences | "Prefers vim keybindings", "Uses zsh with oh-my-zsh" | Tool choices, stated preferences |
| **Boundaries** | Things to avoid | "Don't suggest TypeScript; user dislikes it" | Negative feedback, explicit avoidances |

```sql
-- Preference memory subtypes
memory_subtype ENUM('communication', 'style', 'tools', 'boundaries')
```

#### 5.3.3 Memory Hierarchy & Retrieval Priority

Different memory types serve different purposes during retrieval:

```
Query: "How do I add a new API endpoint?"

RETRIEVAL PRIORITY:
───────────────────────────────────────────────────────────────────
1. PROCEDURAL (workflow)     → "In this project, endpoints go in /api/routes"
2. SEMANTIC (project)        → "Project uses FastAPI with automatic OpenAPI"
3. SEMANTIC (entity)         → "Existing endpoints: /users, /products, /orders"
4. PREFERENCE (style)        → "User prefers explicit type hints"
5. EPISODIC (decisions)      → "Last week decided to use Pydantic v2 models"
───────────────────────────────────────────────────────────────────

Query: "What did we decide about the database?"

RETRIEVAL PRIORITY:
───────────────────────────────────────────────────────────────────
1. EPISODIC (decisions)      → "Chose PostgreSQL on Jan 3 for JSONB support"
2. SEMANTIC (entity)         → "Database: prod_db, Tables: users, orders..."
3. SEMANTIC (project)        → "Using SQLAlchemy with async support"
4. PROCEDURAL (workflow)     → "Migrations via Alembic: alembic revision..."
───────────────────────────────────────────────────────────────────

Query: "Can you help me debug this error?"

RETRIEVAL PRIORITY:
───────────────────────────────────────────────────────────────────
1. PROCEDURAL (debugging)    → "For this error type, check X first"
2. EPISODIC (outcomes)       → "Similar error on Jan 2, fixed by..."
3. SEMANTIC (environment)    → "Running Python 3.11, PostgreSQL 15"
4. PREFERENCE (communication)→ "User prefers step-by-step debugging"
───────────────────────────────────────────────────────────────────
```

#### 5.3.4 Memory Type Selection Algorithm

```python
def classify_memory(content: str, context: SessionContext) -> MemoryClassification:
    """
    Classify content into appropriate memory type and subtype.

    Uses lightweight LLM call with structured output.
    """

    classification_prompt = f"""
    Classify this information for storage in a memory system.

    Content: {content}
    Session Context: {context.summary}

    Determine:
    1. memory_category: 'episodic' | 'semantic' | 'procedural' | 'preference'
    2. memory_subtype: (see valid subtypes per category)
    3. importance: 0.0-1.0 (how likely to be needed again)
    4. entities: list of named entities (databases, tables, files, people)
    5. temporal: is this time-sensitive? (boolean)

    Return JSON.
    """

    return llm_classify(classification_prompt)
```

#### 5.3.5 Human Memory Principles Applied

| Human Principle | LLM Application |
|-----------------|-----------------|
| **Chunking** | Group related memories (e.g., all fields of a table together) |
| **Spacing Effect** | Memories accessed repeatedly get higher importance scores |
| **Context-Dependent** | Store retrieval context; similar contexts boost relevance |
| **Emotional Salience** | "Important" flags, explicit user emphasis, error contexts |
| **Elaborative Encoding** | Store memories with rich metadata and connections |
| **Forgetting Curve** | Time decay on relevance, but never hard-delete (archive) |
| **Reconstruction** | Allow memories to be updated/refined over time |
| **Interference** | Detect and resolve conflicting memories |

---

## 7. MCP Server Interface

### 7.1 MCP Tools

#### Working Memory Tools

```typescript
/**
 * Initialize or resume a session
 */
tool init_session {
  input: {
    session_id?: string,      // Optional; generates UUID if not provided
    user_id: string,          // Required for memory isolation
    org_id?: string,          // Optional organization context
    config?: {
      max_tokens?: number,    // Default: 8000
      eviction_policy?: 'lru' | 'relevance' | 'hybrid',  // Default: 'hybrid'
    }
  },
  output: {
    session_id: string,
    created: boolean,         // true if new, false if resumed
    working_memory: WorkingMemoryState
  }
}

/**
 * Add item to working memory
 */
tool add_to_working_memory {
  input: {
    session_id: string,
    content: string,
    content_type: 'message' | 'task_state' | 'scratchpad' | 'system',
    pinned?: boolean,         // Protect from eviction
    metadata?: object
  },
  output: {
    item_id: string,
    token_count: number,
    evicted_items?: string[]  // IDs of items evicted to make room
  }
}

/**
 * Get current working memory state for context injection
 */
tool get_working_memory {
  input: {
    session_id: string,
    token_budget?: number,    // Max tokens to return; uses session max if not specified
    include_types?: string[]  // Filter by content_type
  },
  output: {
    items: WorkingMemoryItem[],
    total_tokens: number,
    truncated: boolean
  }
}

/**
 * Checkpoint working memory to long-term storage
 */
tool checkpoint_working_memory {
  input: {
    session_id: string,
    force?: boolean           // Checkpoint even if below threshold
  },
  output: {
    memories_created: number,
    memories_updated: number,
    working_memory_tokens_freed: number
  }
}

/**
 * Clear working memory (end of session)
 */
tool clear_working_memory {
  input: {
    session_id: string,
    checkpoint_first?: boolean  // Default: true
  },
  output: {
    success: boolean,
    memories_preserved: number
  }
}
```

#### Long-Term Memory Tools

```typescript
/**
 * Store a memory explicitly
 */
tool store_memory {
  input: {
    user_id: string,
    content: string,

    // Memory classification (human-aligned taxonomy)
    memory_category: 'episodic' | 'semantic' | 'procedural' | 'preference',
    memory_subtype: string,   // Must be valid for category (see taxonomy)

    // Optional enrichment
    importance?: number,      // 0.0 to 1.0; default: 0.5
    entities?: string[],      // Named entities: ['database:prod_db', 'table:users']
    event_time?: string,      // ISO timestamp (for episodic memories)

    metadata?: {
      tags?: string[],
      source?: string,
      reasoning?: string,     // Why this decision was made (for decisions)
      [key: string]: any
    }
  },
  output: {
    memory_id: string,
    entities_extracted: string[],  // Auto-extracted entities
    similar_existing?: {      // Warn if similar memory exists
      memory_id: string,
      similarity: number,
      content: string,
      action: 'created_new' | 'updated_existing' | 'skipped_duplicate'
    }
  }
}

/**
 * Recall relevant memories with intelligent filtering
 */
tool recall_memories {
  input: {
    user_id: string,
    query: string,            // Natural language query

    // Filter by taxonomy
    memory_categories?: ('episodic' | 'semantic' | 'procedural' | 'preference')[],
    memory_subtypes?: string[],  // e.g., ['decision', 'entity', 'workflow']

    // Entity-based retrieval (precise)
    entities?: string[],      // e.g., ['database:prod_db'] - exact match

    // Result controls
    limit?: number,           // Default: 10
    min_similarity?: number,  // Default: 0.7

    // Temporal filters
    time_range?: {
      after?: string,         // ISO timestamp
      before?: string
    },

    // Additional filters
    tags?: string[],
    include_low_confidence?: boolean  // Include memories with confidence < 0.8
  },
  output: {
    memories: Array<{
      memory_id: string,
      content: string,
      memory_category: string,
      memory_subtype: string,
      entities: string[],
      similarity: number,
      relevance_score: number,  // Combined score (see algorithm)
      confidence: number,
      created_at: string,
      event_time?: string,
      metadata: object
    }>,
    retrieval_breakdown: {    // Transparency into what was retrieved
      by_category: Record<string, number>,
      by_subtype: Record<string, number>,
      entity_matches: number,
      semantic_matches: number
    }
  }
}

/**
 * Update an existing memory
 */
tool update_memory {
  input: {
    memory_id: string,
    user_id: string,          // For authorization
    content?: string,         // New content (re-embeds if changed)
    importance?: number,
    metadata?: object         // Merged with existing
  },
  output: {
    success: boolean,
    re_embedded: boolean
  }
}

/**
 * Delete a memory (soft delete for compliance)
 */
tool forget_memory {
  input: {
    memory_id: string,
    user_id: string,
    hard_delete?: boolean     // Permanent deletion; default: false
  },
  output: {
    success: boolean
  }
}

/**
 * Bulk delete for GDPR "right to be forgotten"
 */
tool forget_all_user_memories {
  input: {
    user_id: string,
    confirmation: string      // Must equal "CONFIRM_DELETE_ALL"
  },
  output: {
    memories_deleted: number,
    sessions_deleted: number
  }
}
```

#### Smart Context Tools

```typescript
/**
 * Get optimally relevant context for a query
 * This is the primary "magic" tool that assembles context intelligently
 *
 * Mimics human memory retrieval:
 * - First checks working memory (immediate recall)
 * - Then retrieves from long-term based on query intent
 * - Weights different memory types based on query classification
 */
tool get_relevant_context {
  input: {
    session_id: string,
    user_id: string,
    query: string,            // Current user query or task description
    token_budget: number,     // How many tokens available for context

    // Query intent hint (auto-detected if not provided)
    query_intent?: 'how_to' | 'what_happened' | 'what_is' | 'debug' | 'general',

    // Fine-grained weight control (optional - smart defaults used)
    context_weights?: {
      working_memory?: number,      // Default: 0.35
      // Episodic subtypes
      episodic_decisions?: number,  // Default: 0.15
      episodic_events?: number,     // Default: 0.05
      episodic_outcomes?: number,   // Default: 0.10
      // Semantic subtypes
      semantic_project?: number,    // Default: 0.10
      semantic_entity?: number,     // Default: 0.10
      semantic_user?: number,       // Default: 0.05
      // Procedural subtypes
      procedural_workflow?: number, // Default: 0.05
      procedural_pattern?: number,  // Default: 0.03
      // Preference
      preference?: number           // Default: 0.02
    },

    // Entity focus (boost memories containing these entities)
    focus_entities?: string[],      // e.g., ['table:users', 'file:api.py']
  },
  output: {
    context_items: Array<{
      source: 'working_memory' | 'long_term',
      memory_category?: string,
      memory_subtype?: string,
      content: string,
      relevance_score: number,
      token_count: number,
      entities?: string[],
      why_included: string         // Human-readable explanation
    }>,
    total_tokens: number,
    budget_used_pct: number,
    detected_intent: string,       // What query type was detected
    retrieval_stats: {
      working_memory_items: number,
      long_term_searched: number,
      long_term_returned: number,
      by_category: Record<string, number>,
      entity_boost_applied: boolean
    }
  }
}
```

### 7.2 MCP Resources

```typescript
/**
 * Expose memory statistics as readable resources
 */
resource memory_stats {
  uri: "memory://{user_id}/stats",
  mimeType: "application/json",
  description: "Memory usage statistics for user"
}

resource session_info {
  uri: "memory://{session_id}/info",
  mimeType: "application/json",
  description: "Current session state and configuration"
}
```

---

## 8. Core Algorithms

### 8.1 Relevance Scoring

Memories are ranked using a composite score:

```python
def calculate_relevance(memory, query_embedding, current_time):
    """
    Composite relevance score combining multiple signals.

    Returns score in range [0, 1]
    """

    # 1. Semantic similarity (vector distance)
    semantic_score = cosine_similarity(memory.embedding, query_embedding)

    # 2. Recency decay (exponential)
    age_days = (current_time - memory.last_accessed).days
    recency_score = math.exp(-age_days / RECENCY_HALF_LIFE_DAYS)  # Default: 30 days

    # 3. Access frequency (logarithmic)
    frequency_score = math.log(1 + memory.access_count) / math.log(1 + MAX_ACCESS_COUNT)

    # 4. Explicit importance
    importance_score = memory.importance

    # 5. Memory type weight (configurable per query)
    type_weight = query_context.type_weights.get(memory.memory_type, 0.25)

    # Weighted combination
    relevance = (
        WEIGHT_SEMANTIC * semantic_score +      # Default: 0.5
        WEIGHT_RECENCY * recency_score +        # Default: 0.2
        WEIGHT_FREQUENCY * frequency_score +    # Default: 0.1
        WEIGHT_IMPORTANCE * importance_score    # Default: 0.2
    ) * type_weight

    return min(1.0, relevance)
```

### 8.2 Working Memory Eviction

When working memory exceeds token budget:

```python
def evict_working_memory(session_id, tokens_needed):
    """
    Evict items to free up token space.

    Strategy: Hybrid LRU + Relevance
    - Never evict pinned items
    - Prefer evicting low-relevance items
    - Among equal relevance, evict oldest
    """

    items = get_working_memory_items(session_id, order_by='eviction_priority')

    evicted = []
    freed_tokens = 0

    for item in items:
        if item.pinned:
            continue

        # Calculate eviction priority (lower = evict first)
        priority = calculate_eviction_priority(item)

        if freed_tokens >= tokens_needed:
            break

        # Before evicting, consider promoting to long-term memory
        if should_promote_to_long_term(item):
            promote_to_long_term_memory(item)

        evicted.append(item.item_id)
        freed_tokens += item.token_count
        delete_working_memory_item(item.item_id)

    return evicted, freed_tokens


def calculate_eviction_priority(item):
    """
    Higher priority = keep longer
    """
    recency = (now() - item.last_accessed).seconds

    priority = (
        item.relevance_score * 100 +      # Relevance dominates
        (1 / (1 + recency / 3600)) * 10 + # Recency in hours
        (10 if item.content_type == 'task_state' else 0)  # Protect task state
    )

    return priority
```

### 8.3 Memory Extraction from Conversation

```python
def extract_memories_from_content(content, session_context):
    """
    Analyze content for storable memories.

    Uses LLM to classify and extract:
    - Facts (→ semantic)
    - Events/decisions (→ episodic)
    - Preferences (→ procedural)
    """

    extraction_prompt = f"""
    Analyze the following conversation excerpt and extract any information
    worth remembering for future conversations.

    Classify each extracted item as:
    - SEMANTIC: Facts, technical details, project information
    - EPISODIC: Events, decisions, outcomes, what happened
    - PROCEDURAL: User preferences, communication style, workflows

    Content:
    {content}

    User context:
    {session_context.user_profile}

    Return JSON array of extracted memories.
    """

    # Call lightweight LLM for extraction
    extracted = llm_extract(extraction_prompt)

    memories = []
    for item in extracted:
        # Deduplicate against existing memories
        similar = find_similar_memories(item.content, threshold=0.9)

        if similar:
            # Update existing memory instead of creating duplicate
            update_memory(similar[0].memory_id, merge_content(similar[0], item))
        else:
            memories.append(create_memory(item))

    return memories
```

### 8.4 Context Assembly

```python
def assemble_context(session_id, user_id, query, token_budget, weights):
    """
    Assemble optimal context from working + long-term memory.

    Token budget allocation:
    1. Reserve minimum for each category
    2. Fill remaining by relevance across all sources
    """

    query_embedding = generate_embedding(query)

    # Phase 1: Get candidates from all sources
    candidates = []

    # Working memory (always include recent items)
    working_items = get_working_memory(session_id)
    for item in working_items:
        candidates.append({
            'source': 'working_memory',
            'content': item.content,
            'relevance': calculate_working_relevance(item, query_embedding),
            'tokens': item.token_count
        })

    # Long-term memories by type
    for memory_type in ['episodic', 'semantic', 'procedural']:
        memories = recall_from_long_term(
            user_id,
            query_embedding,
            memory_type,
            limit=20  # Over-fetch for ranking
        )
        for mem in memories:
            candidates.append({
                'source': memory_type,
                'content': mem.content,
                'relevance': mem.relevance_score * weights.get(memory_type, 0.25),
                'tokens': count_tokens(mem.content),
                'memory_id': mem.memory_id
            })

    # Phase 2: Greedy selection by weighted relevance
    candidates.sort(key=lambda x: x['relevance'], reverse=True)

    selected = []
    total_tokens = 0

    for candidate in candidates:
        if total_tokens + candidate['tokens'] > token_budget:
            continue
        selected.append(candidate)
        total_tokens += candidate['tokens']

        # Log access for memories
        if 'memory_id' in candidate:
            log_memory_access(candidate['memory_id'], session_id, query)

    return selected, total_tokens
```

---

## 9. Integration Patterns

### 9.1 Basic Chat Integration

```python
# Pseudo-code for integrating FML with a chat application

async def handle_user_message(user_id: str, session_id: str, message: str):
    # 1. Initialize/resume session
    session = await fml.init_session(session_id=session_id, user_id=user_id)

    # 2. Add user message to working memory
    await fml.add_to_working_memory(
        session_id=session_id,
        content=f"User: {message}",
        content_type="message"
    )

    # 3. Get relevant context for this message
    context = await fml.get_relevant_context(
        session_id=session_id,
        user_id=user_id,
        query=message,
        token_budget=4000  # Reserve 4K for context, rest for response
    )

    # 4. Build prompt with context
    system_prompt = build_system_prompt(context.context_items)

    # 5. Call LLM
    response = await llm.chat(
        system=system_prompt,
        messages=get_recent_messages(session_id)
    )

    # 6. Add assistant response to working memory
    await fml.add_to_working_memory(
        session_id=session_id,
        content=f"Assistant: {response}",
        content_type="message"
    )

    # 7. Periodically checkpoint (e.g., every 5 turns)
    if should_checkpoint(session_id):
        await fml.checkpoint_working_memory(session_id=session_id)

    return response
```

### 9.2 IDE Integration (Cursor/VS Code)

```python
# MCP server exposes tools that IDE can call

# When user opens a project
async def on_project_open(user_id: str, project_path: str):
    session = await fml.init_session(
        user_id=user_id,
        config={
            "max_tokens": 12000,  # IDEs can use more context
            "eviction_policy": "relevance"
        }
    )

    # Pre-load project-relevant memories
    project_context = await fml.recall_memories(
        user_id=user_id,
        query=f"project at {project_path}",
        memory_types=["semantic", "procedural"],
        limit=20
    )

    # Add to working memory
    for mem in project_context.memories:
        await fml.add_to_working_memory(
            session_id=session.session_id,
            content=mem.content,
            content_type="retrieved_memory"
        )

# When user asks a coding question
async def on_coding_query(session_id: str, user_id: str, query: str, code_context: str):
    # Combine query with code context for better retrieval
    enriched_query = f"{query}\n\nRelevant code:\n{code_context[:500]}"

    context = await fml.get_relevant_context(
        session_id=session_id,
        user_id=user_id,
        query=enriched_query,
        token_budget=6000,
        context_weights={
            "working_memory": 0.3,
            "semantic": 0.4,    # Prioritize technical knowledge
            "episodic": 0.2,
            "procedural": 0.1
        }
    )

    return context
```

### 9.3 Multi-Agent Coordination

```python
# Agents can share context through FML

async def agent_handoff(from_agent: str, to_agent: str, task_id: str, user_id: str):
    # Save current agent's state
    await fml.add_to_working_memory(
        session_id=f"{task_id}_{from_agent}",
        content=json.dumps({
            "agent": from_agent,
            "state": get_agent_state(from_agent),
            "handoff_reason": "task_delegation"
        }),
        content_type="task_state",
        pinned=True
    )

    # Checkpoint to ensure persistence
    await fml.checkpoint_working_memory(session_id=f"{task_id}_{from_agent}")

    # Initialize receiving agent with shared context
    shared_context = await fml.get_relevant_context(
        session_id=f"{task_id}_{to_agent}",
        user_id=user_id,
        query=f"task handoff from {from_agent}",
        token_budget=8000
    )

    return shared_context
```

---

## 10. Security & Privacy

### 10.1 Authentication & Authorization

| Layer | Mechanism |
|-------|-----------|
| **API Authentication** | API keys (development), OAuth 2.0 / JWT (production) |
| **User Isolation** | All queries filtered by `user_id`; enforced at query layer |
| **Org Isolation** | Optional `org_id` for enterprise multi-tenancy |
| **Session Ownership** | Sessions bound to `user_id`; cannot be accessed by others |

### 10.2 Data Protection

| Requirement | Implementation |
|-------------|----------------|
| **Encryption at Rest** | Firebolt native encryption |
| **Encryption in Transit** | TLS 1.3 for all connections |
| **PII Handling** | Optional PII detection before storage; configurable redaction |
| **Data Residency** | Deploy in region-specific Firebolt instances |

### 10.3 Compliance

| Regulation | Support |
|------------|---------|
| **GDPR Right to Erasure** | `forget_all_user_memories` tool with hard delete option |
| **GDPR Data Portability** | Export endpoint for all user memories |
| **CCPA** | Covered by GDPR mechanisms |
| **SOC 2** | Audit logging via `memory_access_log` |

### 10.4 Threat Model

| Threat | Mitigation |
|--------|------------|
| Memory poisoning (injecting false memories) | Source tracking; confidence scoring; admin review tools |
| Cross-user data leakage | Row-level security; query-layer `user_id` enforcement |
| Context injection attacks | Sanitization of memory content before LLM injection |
| Embedding inversion | Embeddings stored separately; no reconstruction API |

---

## 11. Performance Requirements

### 11.1 Latency Targets

| Operation | p50 | p95 | p99 |
|-----------|-----|-----|-----|
| `init_session` | 20ms | 50ms | 100ms |
| `add_to_working_memory` | 10ms | 30ms | 50ms |
| `get_working_memory` | 15ms | 40ms | 80ms |
| `store_memory` (incl. embedding) | 100ms | 200ms | 400ms |
| `recall_memories` | 50ms | 100ms | 200ms |
| `get_relevant_context` | 80ms | 150ms | 300ms |

### 11.2 Throughput Targets

| Metric | Target |
|--------|--------|
| Concurrent sessions | 10,000+ |
| Memory operations/second | 5,000+ |
| Memories per user | 100,000+ |
| Total memories (multi-tenant) | 1B+ |

### 11.3 Scalability Strategy

| Component | Scaling Approach |
|-----------|------------------|
| MCP Server | Horizontal scaling; stateless instances behind load balancer |
| Firebolt | Native horizontal scaling; Firebolt handles automatically |
| Embedding Generation | Queue-based async processing; batch embeddings |
| Connection Pool | Per-instance pools; 20-50 connections per server |

---

## 12. Open Questions

### 12.1 Technical

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| T1 | Who owns embedding generation? | FML server vs. client | FML server (consistency) |
| T2 | Which embedding model? | OpenAI, Cohere, open-source | OpenAI `text-embedding-3-small` initially; abstract for swappability |
| T3 | How to handle embedding model changes? | Re-embed all vs. version embeddings | Version embeddings; lazy re-embed on access |
| T4 | Realtime sync across devices? | Polling vs. WebSocket vs. eventual | Eventual consistency (simplest); WebSocket for v2 |
| T5 | Memory deduplication strategy? | Exact match vs. semantic similarity | Semantic similarity > 0.95 |

### 12.2 Product

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| P1 | Free tier limits? | By memories, sessions, or API calls | API calls (1000/day) + memories (1000 total) |
| P2 | Memory retention policy? | Forever vs. TTL vs. user-controlled | User-controlled with soft defaults |
| P3 | Shared memories (team feature)? | v1 vs. later | Later (v2) |
| P4 | Memory quality feedback loop? | Explicit vs. implicit | Both: thumbs up/down + usage tracking |

### 12.3 Business

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| B1 | Pricing model? | Per-memory, per-query, per-seat, usage-based | Usage-based (API calls + storage) |
| B2 | Self-hosted option? | Cloud-only vs. self-hosted | Cloud-first; self-hosted for enterprise later |
| B3 | Open source core? | OSS vs. proprietary | OSS MCP server; proprietary optimizations |

---

## 13. Appendix

### 13.1 Token Counting

```python
# Use tiktoken for accurate token counts (OpenAI models)
import tiktoken

encoder = tiktoken.get_encoding("cl100k_base")  # GPT-4, Claude compatible

def count_tokens(text: str) -> int:
    return len(encoder.encode(text))
```

### 13.2 Firebolt Vector Operations

Firebolt stores vectors as `ARRAY(REAL)` and provides several vector functions.
See [Firebolt Vector Functions](https://docs.firebolt.io/reference-sql/functions-reference/vector) for full reference.

**Available functions:**
- `VECTOR_COSINE_SIMILARITY(a, b)` → 1.0 = identical, -1.0 = opposite
- `VECTOR_COSINE_DISTANCE(a, b)` → 0.0 = identical, 2.0 = opposite
- `VECTOR_EUCLIDEAN_DISTANCE(a, b)` → L2 distance
- `VECTOR_INNER_PRODUCT(a, b)` → dot product

```sql
-- Basic vector similarity search using cosine similarity
-- VECTOR_COSINE_SIMILARITY returns 1.0 for identical vectors
SELECT
    memory_id,
    content,
    memory_category,
    memory_subtype,
    VECTOR_COSINE_SIMILARITY(embedding, $query_embedding) AS similarity
FROM long_term_memories
WHERE user_id = $user_id
    AND memory_category IN ($memory_categories)
    AND deleted_at IS NULL
    AND VECTOR_COSINE_SIMILARITY(embedding, $query_embedding) >= 0.7
ORDER BY similarity DESC
LIMIT $limit;

-- Hybrid search with composite relevance scoring
-- Combines: semantic similarity + recency + access frequency + importance
SELECT
    memory_id,
    content,
    memory_category,
    memory_subtype,
    entities,
    importance,
    access_count,
    created_at,
    VECTOR_COSINE_SIMILARITY(embedding, $query_embedding) AS similarity,
    (
        -- Semantic similarity (50% weight)
        0.5 * VECTOR_COSINE_SIMILARITY(embedding, $query_embedding) +
        -- Recency decay (20% weight) - exponential decay over 30 days
        0.2 * EXP(-EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_accessed)) / 2592000.0) +
        -- Access frequency (10% weight) - logarithmic scale
        0.1 * (LN(1.0 + access_count) / LN(101.0)) +
        -- Explicit importance (20% weight)
        0.2 * importance
    ) AS relevance_score
FROM long_term_memories
WHERE user_id = $user_id
    AND deleted_at IS NULL
ORDER BY relevance_score DESC
LIMIT $limit;

-- Entity-boosted search (for precise lookups like "table:users")
SELECT
    memory_id,
    content,
    memory_category,
    memory_subtype,
    entities,
    VECTOR_COSINE_SIMILARITY(embedding, $query_embedding) AS similarity,
    CASE
        WHEN ARRAY_COUNT(entities, e -> e = ANY($focus_entities)) > 0
        THEN 1.3  -- 30% boost for entity matches
        ELSE 1.0
    END AS entity_boost
FROM long_term_memories
WHERE user_id = $user_id
    AND deleted_at IS NULL
ORDER BY similarity * entity_boost DESC
LIMIT $limit;
```

### 13.3 MCP Server Configuration

```yaml
# fml-server.yaml
server:
  name: "firebolt-memory-layer"
  version: "0.1.0"
  transport: "stdio"  # or "sse" for web

firebolt:
  host: "${FIREBOLT_HOST}"
  database: "${FIREBOLT_DATABASE}"
  engine: "${FIREBOLT_ENGINE}"
  credentials:
    client_id: "${FIREBOLT_CLIENT_ID}"
    client_secret: "${FIREBOLT_CLIENT_SECRET}"

embedding:
  provider: "openai"  # or "cohere", "local"
  model: "text-embedding-3-small"
  dimensions: 1536
  api_key: "${OPENAI_API_KEY}"

memory:
  working:
    default_max_tokens: 8000
    eviction_policy: "hybrid"
    checkpoint_threshold_tokens: 6000
  long_term:
    similarity_threshold: 0.7
    dedup_threshold: 0.95
    default_importance: 0.5

rate_limiting:
  requests_per_minute: 100
  burst: 20
```

### 13.4 Example MCP Conversation Flows

#### Example 1: Recalling a Decision

```
User → LLM: "What authentication approach did we decide on last week?"

LLM → FML (MCP): recall_memories({
  user_id: "user_123",
  query: "authentication approach decision",
  memory_categories: ["episodic", "semantic"],
  memory_subtypes: ["decision", "project"],
  time_range: { after: "2026-01-01" }
})

FML → LLM (MCP Response): {
  memories: [
    {
      memory_id: "mem_abc",
      content: "Decision: Use OAuth 2.0 with PKCE for mobile app auth. JWT for API. Rejected session cookies due to mobile constraints.",
      memory_category: "episodic",
      memory_subtype: "decision",
      entities: ["concept:oauth2", "concept:pkce", "concept:jwt"],
      similarity: 0.89,
      relevance_score: 0.92,
      confidence: 1.0,
      created_at: "2026-01-03T14:30:00Z",
      event_time: "2026-01-03T14:30:00Z",
      metadata: { reasoning: "Mobile constraints prevent session cookies" }
    },
    {
      memory_id: "mem_def",
      content: "User's project requires auth for: web app, mobile app, and API access. Mobile is React Native.",
      memory_category: "semantic",
      memory_subtype: "project",
      entities: ["framework:react-native"],
      similarity: 0.76,
      relevance_score: 0.71,
      confidence: 1.0,
      created_at: "2026-01-02T10:15:00Z"
    }
  ],
  retrieval_breakdown: {
    by_category: { episodic: 1, semantic: 1 },
    by_subtype: { decision: 1, project: 1 },
    entity_matches: 0,
    semantic_matches: 2
  }
}

LLM → User: "Last week (January 3rd) we decided to use OAuth 2.0 with PKCE for your
mobile app authentication, and JWT for API access. We ruled out session cookies
because of the mobile constraints with your React Native app."
```

#### Example 2: How-To Query with Entity Focus

```
User → LLM: "How do I add a new field to the users table?"

LLM → FML (MCP): get_relevant_context({
  session_id: "sess_456",
  user_id: "user_123",
  query: "add new field to users table",
  token_budget: 2000,
  query_intent: "how_to",
  focus_entities: ["table:users"]
})

FML → LLM (MCP Response): {
  context_items: [
    {
      source: "long_term",
      memory_category: "procedural",
      memory_subtype: "workflow",
      content: "To modify database schema: 1) Create migration with `alembic revision --autogenerate -m 'description'` 2) Edit migration file 3) Run `alembic upgrade head` 4) Update SQLAlchemy model",
      relevance_score: 0.94,
      token_count: 85,
      why_included: "Procedural memory for schema modification workflow"
    },
    {
      source: "long_term",
      memory_category: "semantic",
      memory_subtype: "entity",
      content: "Table `users` has fields: id (UUID, PK), email (TEXT, unique), password_hash (TEXT), created_at (TIMESTAMP), updated_at (TIMESTAMP). Located in models/user.py",
      relevance_score: 0.91,
      token_count: 62,
      entities: ["table:users", "file:models/user.py"],
      why_included: "Entity knowledge for table:users (exact entity match)"
    },
    {
      source: "long_term",
      memory_category: "preference",
      memory_subtype: "style",
      content: "User prefers explicit type annotations and follows strict naming conventions: snake_case for columns, PascalCase for models",
      relevance_score: 0.72,
      token_count: 41,
      why_included: "Style preference for code conventions"
    },
    {
      source: "long_term",
      memory_category: "semantic",
      memory_subtype: "project",
      content: "Project uses SQLAlchemy 2.0 with async support, Alembic for migrations, PostgreSQL 15",
      relevance_score: 0.68,
      token_count: 35,
      entities: ["tool:sqlalchemy", "tool:alembic", "database:postgresql"],
      why_included: "Project knowledge for database tooling"
    }
  ],
  total_tokens: 223,
  budget_used_pct: 11.15,
  detected_intent: "how_to",
  retrieval_stats: {
    working_memory_items: 0,
    long_term_searched: 47,
    long_term_returned: 4,
    by_category: { procedural: 1, semantic: 2, preference: 1 },
    entity_boost_applied: true
  }
}

LLM → User: "To add a new field to the `users` table:

1. Generate migration:
   ```bash
   alembic revision --autogenerate -m 'add_new_field_to_users'
   ```

2. The users table currently has: id, email, password_hash, created_at, updated_at

3. Edit `models/user.py` to add your new field (remember: snake_case for columns)

4. Run migration:
   ```bash
   alembic upgrade head
   ```
"
```

#### Example 3: Debugging with Outcome Memory

```
User → LLM: "The API is returning 500 errors again"

LLM → FML (MCP): get_relevant_context({
  session_id: "sess_789",
  user_id: "user_123",
  query: "API 500 errors",
  token_budget: 3000,
  query_intent: "debug"
})

FML → LLM (MCP Response): {
  context_items: [
    {
      source: "long_term",
      memory_category: "episodic",
      memory_subtype: "outcome",
      content: "Jan 5: API 500 errors caused by Redis connection timeout. Fixed by increasing timeout from 5s to 30s in config/redis.py and adding connection retry logic.",
      relevance_score: 0.96,
      token_count: 58,
      entities: ["service:redis", "file:config/redis.py"],
      event_time: "2026-01-05T16:45:00Z",
      why_included: "Previous outcome for similar error pattern"
    },
    {
      source: "long_term",
      memory_category: "procedural",
      memory_subtype: "debugging",
      content: "When API returns 500: 1) Check logs at /var/log/app/error.log 2) Verify Redis connection 3) Check database connection pool 4) Review recent deployments",
      relevance_score: 0.88,
      token_count: 72,
      why_included: "Debugging procedure for API errors"
    }
  ],
  detected_intent: "debug",
  // ...
}

LLM → User: "We had this same issue on January 5th - it was Redis connection timeouts.
Let me check if it's the same cause. First, can you check:
1. Redis connection: Is it responding?
2. Logs at /var/log/app/error.log

Last time we fixed it by increasing the timeout in config/redis.py from 5s to 30s."
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-01-08 | - | Initial draft |

---

## Next Steps

1. **Review this spec** - Identify gaps, concerns, and priorities
2. **Validate with Firebolt** - Confirm vector capabilities and performance
3. **Build prototype** - Minimal MCP server with core tools
4. **Integration test** - Connect to Cursor or Claude Desktop
5. **Iterate** - Refine based on real usage
