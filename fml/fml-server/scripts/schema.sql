-- ============================================================
-- FML Server Database Schema for Firebolt
-- Uses Firebolt-specific syntax (PRIMARY INDEX, no PRIMARY KEY)
-- ============================================================

-- ============================================================
-- WORKING MEMORY TABLES
-- ============================================================

-- Session management
CREATE TABLE IF NOT EXISTS session_contexts (
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    org_id          TEXT,

    total_tokens    INT DEFAULT 0,
    max_tokens      INT DEFAULT 8000,

    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    last_activity   TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    expires_at      TIMESTAMPNTZ,

    config          TEXT
)
PRIMARY INDEX session_id;

-- Working memory items
CREATE TABLE IF NOT EXISTS working_memory_items (
    item_id         TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,

    content_type    TEXT NOT NULL,
    content         TEXT NOT NULL,
    token_count     INT NOT NULL,

    relevance_score REAL DEFAULT 1.0,
    pinned          BOOLEAN DEFAULT FALSE,

    sequence_num    INT NOT NULL,
    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    last_accessed   TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP()
)
PRIMARY INDEX item_id;


-- ============================================================
-- LONG-TERM MEMORY TABLES
-- ============================================================

-- Main memory table with vector embeddings
-- NOTE: embedding column is NOT NULL to support HNSW vector search index
CREATE TABLE IF NOT EXISTS long_term_memories (
    memory_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    org_id          TEXT,

    -- Memory classification (human-aligned taxonomy)
    memory_category TEXT NOT NULL,
    memory_subtype  TEXT NOT NULL,

    -- Content
    content         TEXT NOT NULL,
    summary         TEXT,

    -- Vector embedding: ARRAY(REAL NOT NULL) NOT NULL for 1536-dim OpenAI embeddings
    -- Must be NOT NULL (inner and outer) to support vector search index
    embedding       ARRAY(REAL NOT NULL) NOT NULL,

    -- Named entities for precise retrieval
    entities        ARRAY(TEXT),

    -- Metadata as JSON string
    metadata        TEXT,

    -- Temporal context
    event_time      TIMESTAMPNTZ,
    is_temporal     BOOLEAN DEFAULT FALSE,

    -- Importance & access patterns
    importance      REAL DEFAULT 0.5,
    access_count    INT DEFAULT 0,
    decay_factor    REAL DEFAULT 1.0,

    -- Relationships
    related_memories ARRAY(TEXT),
    supersedes      TEXT,

    -- Source tracking
    source_session  TEXT,
    source_type     TEXT,
    confidence      REAL DEFAULT 1.0,

    -- Timestamps
    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    last_accessed   TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),

    -- Soft delete
    deleted_at      TIMESTAMPNTZ
)
PRIMARY INDEX memory_id;

-- HNSW Vector Search Index for fast semantic similarity search
-- Must be created on empty table before inserting data (Firebolt 4.28)
-- Uses cosine distance for Ollama nomic-embed-text embeddings (768 dimensions)
-- Note: OpenAI embeddings are 1536 dimensions if using that instead
CREATE INDEX idx_memories_embedding ON long_term_memories USING HNSW (
    embedding vector_cosine_ops
) WITH (
    dimension = 768,
    m = 16,
    ef_construction = 128,
    quantization = 'bf16'
);


-- Memory access log for analytics
CREATE TABLE IF NOT EXISTS memory_access_log (
    access_id       TEXT NOT NULL,
    memory_id       TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,

    query_text      TEXT,
    similarity_score REAL,

    was_useful      BOOLEAN,
    was_used        BOOLEAN,

    accessed_at     TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP()
)
PRIMARY INDEX access_id;
