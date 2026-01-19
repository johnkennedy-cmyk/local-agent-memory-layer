# Firebolt Memory Layer (FML) — Prototype Project Plan

**Version:** 0.1
**Created:** January 8, 2026
**Target Duration:** 2-3 weeks for MVP

---

## Overview

This document outlines the plan to build a working prototype of the Firebolt Memory Layer (FML) MCP server. The prototype will demonstrate:

1. **Working memory management** in Firebolt (session-scoped, structured)
2. **Long-term memory storage** with vector embeddings
3. **Intelligent retrieval** using semantic similarity + relevance scoring
4. **MCP integration** for IDE/chatbot connectivity

### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **MCP Server** | Python (FastMCP or custom) | Mature MCP tooling, good Firebolt SDK |
| **Database** | Firebolt | Vector support + fast analytics |
| **Embeddings** | OpenAI `text-embedding-3-small` | Production-quality, 1536 dimensions |
| **Local LLM** | Ollama + Mistral 7B | Categorization, summarization, entity extraction (24GB RAM) |
| **Transport** | stdio (local) → SSE (web) | Start simple, add web later |

---

## Phase 1: Environment Setup (Days 1-2)

### 1.1 Development Environment

```bash
# Create project structure
mkdir -p fml-server/{src,tests,scripts,config}
cd fml-server

# Python environment
python -m venv .venv
source .venv/bin/activate

# Core dependencies
pip install \
    firebolt-sdk \
    openai \
    ollama \
    mcp \
    pydantic \
    python-dotenv \
    tiktoken \
    pytest \
    pytest-asyncio
```

**Files to create:**
- `pyproject.toml` — Project configuration
- `.env.example` — Environment variable template
- `src/__init__.py`
- `src/server.py` — MCP server entry point
- `src/config.py` — Configuration management

### 1.2 Firebolt Setup

**Prerequisites:**
- [ ] Firebolt account with API access
- [ ] Create database: `fml_prototype`
- [ ] Create engine: `fml_engine` (start small, scale later)

**Environment variables:**
```bash
# .env
FIREBOLT_CLIENT_ID=your_client_id
FIREBOLT_CLIENT_SECRET=your_client_secret
FIREBOLT_ACCOUNT=your_account_name
FIREBOLT_DATABASE=fml_prototype
FIREBOLT_ENGINE=fml_engine

OPENAI_API_KEY=your_openai_key

OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral:7b
```

### 1.3 Ollama Setup

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama service
ollama serve

# Pull Mistral 7B for categorization/summarization
# Requires ~4.1GB download, runs well with 24GB RAM
ollama pull mistral:7b
```

**Test Ollama is working:**
```python
import ollama

response = ollama.chat(model='mistral:7b', messages=[
    {'role': 'user', 'content': 'Say "Ollama is working" and nothing else.'}
])
print(response['message']['content'])
```

### 1.4 OpenAI Embeddings Setup

```python
# Test embedding generation
from openai import OpenAI

client = OpenAI()
response = client.embeddings.create(
    model="text-embedding-3-small",
    input="Test embedding generation"
)
print(f"Embedding dimension: {len(response.data[0].embedding)}")  # Should be 1536
```

---

## Phase 2: Database Schema (Days 2-3)

### 2.1 Firebolt Schema Creation

**Firebolt Vector Syntax** (confirmed from [Firebolt docs](https://docs.firebolt.io/reference-sql/functions-reference/vector)):
- Vectors stored as `ARRAY(REAL)` or `ARRAY(DOUBLE PRECISION)`
- Similarity: `VECTOR_COSINE_SIMILARITY(a, b)` → 1.0 = identical
- Distance: `VECTOR_COSINE_DISTANCE(a, b)` → 0.0 = identical
- Also available: `VECTOR_EUCLIDEAN_DISTANCE`, `VECTOR_INNER_PRODUCT`

```sql
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

    config          TEXT,  -- JSON string

    PRIMARY KEY (session_id)
);

-- Working memory items
CREATE TABLE IF NOT EXISTS working_memory_items (
    item_id         TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,

    content_type    TEXT NOT NULL,  -- 'message', 'task_state', 'scratchpad', 'retrieved_memory'
    content         TEXT NOT NULL,
    token_count     INT NOT NULL,

    relevance_score REAL DEFAULT 1.0,
    pinned          BOOLEAN DEFAULT FALSE,

    sequence_num    INT NOT NULL,
    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    last_accessed   TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),

    PRIMARY KEY (item_id)
);

-- Index for efficient session lookups
CREATE INDEX IF NOT EXISTS idx_wmi_session
    ON working_memory_items(session_id, sequence_num);


-- ============================================================
-- LONG-TERM MEMORY TABLES
-- ============================================================

-- Main memory table with vector embeddings
-- Vectors stored as ARRAY(REAL) per Firebolt docs
CREATE TABLE IF NOT EXISTS long_term_memories (
    memory_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    org_id          TEXT,

    -- Memory classification
    memory_category TEXT NOT NULL,  -- 'episodic', 'semantic', 'procedural', 'preference'
    memory_subtype  TEXT NOT NULL,  -- Subtype within category

    -- Content
    content         TEXT NOT NULL,
    summary         TEXT,

    -- Vector embedding: ARRAY(REAL) for 1536-dim OpenAI embeddings
    -- Use VECTOR_COSINE_SIMILARITY() for retrieval
    embedding       ARRAY(REAL),

    -- Named entities for precise retrieval
    entities        ARRAY(TEXT),  -- ['database:prod_db', 'table:users']

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
    source_type     TEXT,  -- 'conversation', 'explicit', 'inferred', 'observed'
    confidence      REAL DEFAULT 1.0,

    -- Timestamps
    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    last_accessed   TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),

    -- Soft delete
    deleted_at      TIMESTAMPNTZ,

    PRIMARY KEY (memory_id)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_ltm_user_category
    ON long_term_memories(user_id, memory_category);

CREATE INDEX IF NOT EXISTS idx_ltm_user_subtype
    ON long_term_memories(user_id, memory_subtype);

-- Note: Firebolt doesn't have dedicated vector indexes yet,
-- but its columnar storage + parallel processing handles vector ops efficiently


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

    accessed_at     TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),

    PRIMARY KEY (access_id)
);
```

### 2.2 Schema Migration Script

```python
# scripts/migrate.py
import os
from firebolt.db import connect
from firebolt.client.auth import ClientCredentials
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return connect(
        auth=ClientCredentials(
            client_id=os.getenv('FIREBOLT_CLIENT_ID'),
            client_secret=os.getenv('FIREBOLT_CLIENT_SECRET')
        ),
        account_name=os.getenv('FIREBOLT_ACCOUNT'),
        database=os.getenv('FIREBOLT_DATABASE'),
        engine_name=os.getenv('FIREBOLT_ENGINE')
    )

def run_migrations():
    conn = get_connection()
    cursor = conn.cursor()

    # Read and execute schema SQL
    with open('scripts/schema.sql', 'r') as f:
        schema_sql = f.read()

    # Split by semicolon and execute each statement
    statements = [s.strip() for s in schema_sql.split(';') if s.strip()]

    for stmt in statements:
        if stmt and not stmt.startswith('--'):
            print(f"Executing: {stmt[:50]}...")
            cursor.execute(stmt)

    print("Migration complete!")
    conn.close()

if __name__ == "__main__":
    run_migrations()
```

---

## Phase 3: Core Services (Days 3-6)

### 3.1 Project Structure

```
fml-server/
├── src/
│   ├── __init__.py
│   ├── server.py           # MCP server entry point
│   ├── config.py           # Configuration
│   ├── db/
│   │   ├── __init__.py
│   │   ├── client.py       # Firebolt connection management
│   │   ├── queries.py      # SQL query builders
│   │   └── models.py       # Pydantic models for DB entities
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── working.py      # Working memory manager
│   │   ├── longterm.py     # Long-term memory manager
│   │   ├── retrieval.py    # Relevance scoring & retrieval
│   │   └── taxonomy.py     # Memory classification
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── embeddings.py   # OpenAI embedding service
│   │   ├── ollama.py       # Ollama integration
│   │   └── prompts.py      # Prompt templates
│   └── tools/
│       ├── __init__.py
│       ├── working_memory.py   # MCP tools for working memory
│       ├── longterm_memory.py  # MCP tools for long-term memory
│       └── context.py          # Smart context assembly tool
├── scripts/
│   ├── schema.sql
│   ├── migrate.py
│   └── seed_test_data.py
├── tests/
│   ├── __init__.py
│   ├── test_working_memory.py
│   ├── test_longterm_memory.py
│   └── test_retrieval.py
├── config/
│   └── fml-server.yaml
├── .env.example
├── pyproject.toml
└── README.md
```

### 3.2 Firebolt Client

```python
# src/db/client.py
import os
from contextlib import contextmanager
from firebolt.db import connect
from firebolt.client.auth import ClientCredentials
from dotenv import load_dotenv

load_dotenv()

class FireboltClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_connection()
        return cls._instance

    def _init_connection(self):
        self.auth = ClientCredentials(
            client_id=os.getenv('FIREBOLT_CLIENT_ID'),
            client_secret=os.getenv('FIREBOLT_CLIENT_SECRET')
        )
        self.account = os.getenv('FIREBOLT_ACCOUNT')
        self.database = os.getenv('FIREBOLT_DATABASE')
        self.engine = os.getenv('FIREBOLT_ENGINE')

    @contextmanager
    def get_cursor(self):
        conn = connect(
            auth=self.auth,
            account_name=self.account,
            database=self.database,
            engine_name=self.engine
        )
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
            conn.close()

    def execute(self, query: str, params: tuple = None):
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()

    def execute_many(self, query: str, params_list: list):
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)


# Singleton instance
db = FireboltClient()
```

### 3.3 Embedding Service (OpenAI)

```python
# src/llm/embeddings.py
import os
from openai import OpenAI
from typing import List
import tiktoken

class EmbeddingService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = "text-embedding-3-small"
        self.dimensions = 1536
        self.encoder = tiktoken.get_encoding("cl100k_base")

        # Simple cache for recent embeddings
        self._cache = {}
        self._cache_max_size = 1000

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoder.encode(text))

    def generate(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        # Check cache
        cache_key = hash(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        embedding = response.data[0].embedding

        # Cache result
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entry (simple FIFO)
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = embedding

        return embedding

    def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        # Filter out cached
        uncached_indices = []
        uncached_texts = []
        results = [None] * len(texts)

        for i, text in enumerate(texts):
            cache_key = hash(text)
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            response = self.client.embeddings.create(
                model=self.model,
                input=uncached_texts
            )
            for idx, embedding_data in zip(uncached_indices, response.data):
                results[idx] = embedding_data.embedding
                self._cache[hash(texts[idx])] = embedding_data.embedding

        return results


# Singleton
embedding_service = EmbeddingService()
```

### 3.4 Ollama Service (Local LLM)

```python
# src/llm/ollama.py
import os
import json
import ollama
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class MemoryClassification(BaseModel):
    memory_category: str  # 'episodic', 'semantic', 'procedural', 'preference'
    memory_subtype: str
    importance: float
    entities: List[str]
    is_temporal: bool
    summary: Optional[str] = None

class OllamaService:
    def __init__(self):
        self.host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.model = os.getenv('OLLAMA_MODEL', 'mistral:7b')

        # Configure ollama client
        ollama.Client(host=self.host)

    def _chat(self, prompt: str, system: str = None) -> str:
        """Send a chat message to Ollama."""
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})

        response = ollama.chat(
            model=self.model,
            messages=messages
        )
        return response['message']['content']

    def classify_memory(self, content: str, context: str = "") -> MemoryClassification:
        """
        Classify content into memory taxonomy.
        Uses local LLM to determine category, subtype, importance, and entities.
        """
        system_prompt = """You are a memory classification system. Analyze the given content and classify it for storage in a long-term memory system.

Return ONLY valid JSON with these fields:
- memory_category: one of 'episodic', 'semantic', 'procedural', 'preference'
- memory_subtype:
  - For episodic: 'event', 'decision', 'conversation', 'outcome'
  - For semantic: 'user', 'project', 'environment', 'domain', 'entity'
  - For procedural: 'workflow', 'pattern', 'tool_usage', 'debugging'
  - For preference: 'communication', 'style', 'tools', 'boundaries'
- importance: float 0.0 to 1.0 (how likely to be needed again)
- entities: array of named entities in format "type:name" (e.g., "database:prod_db", "table:users", "file:api.py", "person:john")
- is_temporal: boolean (is this time-sensitive information?)
- summary: optional shorter version (only if content is long)"""

        prompt = f"""Content to classify:
{content}

Additional context:
{context if context else "None provided"}

Return JSON only, no explanation."""

        response = self._chat(prompt, system_prompt)

        # Parse JSON from response
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                return MemoryClassification(**data)
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback to defaults if parsing fails
            print(f"Warning: Failed to parse LLM response: {e}")
            return MemoryClassification(
                memory_category='semantic',
                memory_subtype='domain',
                importance=0.5,
                entities=[],
                is_temporal=False
            )

    def extract_entities(self, content: str) -> List[str]:
        """Extract named entities from content."""
        system_prompt = """Extract named entities from the content. Return a JSON array of strings in the format "type:name".

Entity types to look for:
- database: database names
- table: table/collection names
- field: column/field names
- file: file paths
- function: function/method names
- class: class names
- api: API endpoints
- service: service names
- person: people's names
- tool: tools/frameworks
- concept: technical concepts

Return ONLY a JSON array, no explanation."""

        prompt = f"Content:\n{content}"

        response = self._chat(prompt, system_prompt)

        try:
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(response[json_start:json_end])
        except json.JSONDecodeError:
            return []

        return []

    def summarize(self, content: str, max_length: int = 100) -> str:
        """Summarize content to fit within token limit."""
        system_prompt = f"""Summarize the following content in {max_length} words or less.
Preserve key facts, decisions, and technical details.
Return only the summary, no preamble."""

        response = self._chat(content, system_prompt)
        return response.strip()

    def detect_query_intent(self, query: str) -> str:
        """Detect the intent of a user query for retrieval optimization."""
        system_prompt = """Classify the query intent. Return ONLY one of these words:
- how_to: asking how to do something
- what_happened: asking about past events/decisions
- what_is: asking for facts/information
- debug: asking for help with an error/problem
- general: other/unclear

Return only the classification word, nothing else."""

        response = self._chat(query, system_prompt)

        intent = response.strip().lower()
        valid_intents = ['how_to', 'what_happened', 'what_is', 'debug', 'general']

        return intent if intent in valid_intents else 'general'


# Singleton
ollama_service = OllamaService()
```

### 3.5 Memory Taxonomy

```python
# src/memory/taxonomy.py
from enum import Enum
from typing import Dict, List

class MemoryCategory(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PREFERENCE = "preference"

class EpisodicSubtype(str, Enum):
    EVENT = "event"
    DECISION = "decision"
    CONVERSATION = "conversation"
    OUTCOME = "outcome"

class SemanticSubtype(str, Enum):
    USER = "user"
    PROJECT = "project"
    ENVIRONMENT = "environment"
    DOMAIN = "domain"
    ENTITY = "entity"

class ProceduralSubtype(str, Enum):
    WORKFLOW = "workflow"
    PATTERN = "pattern"
    TOOL_USAGE = "tool_usage"
    DEBUGGING = "debugging"

class PreferenceSubtype(str, Enum):
    COMMUNICATION = "communication"
    STYLE = "style"
    TOOLS = "tools"
    BOUNDARIES = "boundaries"

# Retrieval weight profiles based on query intent
INTENT_WEIGHTS: Dict[str, Dict[str, float]] = {
    "how_to": {
        "working_memory": 0.25,
        "procedural.workflow": 0.25,
        "procedural.pattern": 0.15,
        "semantic.project": 0.15,
        "semantic.entity": 0.10,
        "preference.style": 0.05,
        "episodic.decision": 0.05,
    },
    "what_happened": {
        "working_memory": 0.20,
        "episodic.decision": 0.30,
        "episodic.event": 0.20,
        "episodic.outcome": 0.15,
        "semantic.project": 0.10,
        "episodic.conversation": 0.05,
    },
    "what_is": {
        "working_memory": 0.20,
        "semantic.entity": 0.30,
        "semantic.project": 0.20,
        "semantic.domain": 0.15,
        "semantic.environment": 0.10,
        "episodic.decision": 0.05,
    },
    "debug": {
        "working_memory": 0.30,
        "procedural.debugging": 0.25,
        "episodic.outcome": 0.20,
        "semantic.environment": 0.10,
        "semantic.entity": 0.10,
        "preference.tools": 0.05,
    },
    "general": {
        "working_memory": 0.35,
        "semantic.project": 0.15,
        "episodic.decision": 0.15,
        "semantic.entity": 0.10,
        "procedural.workflow": 0.10,
        "preference.communication": 0.10,
        "semantic.user": 0.05,
    }
}

def get_retrieval_weights(intent: str) -> Dict[str, float]:
    """Get retrieval weights for a query intent."""
    return INTENT_WEIGHTS.get(intent, INTENT_WEIGHTS["general"])

def validate_subtype(category: str, subtype: str) -> bool:
    """Validate that subtype is valid for category."""
    valid_subtypes = {
        "episodic": [e.value for e in EpisodicSubtype],
        "semantic": [e.value for e in SemanticSubtype],
        "procedural": [e.value for e in ProceduralSubtype],
        "preference": [e.value for e in PreferenceSubtype],
    }
    return subtype in valid_subtypes.get(category, [])
```

---

## Phase 4: MCP Tools Implementation (Days 6-9)

### 4.1 MCP Server Setup

```python
# src/server.py
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server

from src.tools.working_memory import register_working_memory_tools
from src.tools.longterm_memory import register_longterm_memory_tools
from src.tools.context import register_context_tools

# Create server instance
server = Server("firebolt-memory-layer")

# Register all tools
register_working_memory_tools(server)
register_longterm_memory_tools(server)
register_context_tools(server)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### 4.2 Working Memory Tools

```python
# src/tools/working_memory.py
from mcp.server import Server
from mcp.types import Tool, TextContent
from pydantic import BaseModel
from typing import Optional, List
import uuid
import json

from src.db.client import db
from src.llm.embeddings import embedding_service

class InitSessionInput(BaseModel):
    session_id: Optional[str] = None
    user_id: str
    org_id: Optional[str] = None
    max_tokens: int = 8000

class AddToWorkingMemoryInput(BaseModel):
    session_id: str
    content: str
    content_type: str  # 'message', 'task_state', 'scratchpad', 'system'
    pinned: bool = False

class GetWorkingMemoryInput(BaseModel):
    session_id: str
    token_budget: Optional[int] = None

def register_working_memory_tools(server: Server):

    @server.tool()
    async def init_session(
        user_id: str,
        session_id: Optional[str] = None,
        org_id: Optional[str] = None,
        max_tokens: int = 8000
    ) -> str:
        """Initialize or resume a memory session."""

        sid = session_id or str(uuid.uuid4())

        # Check if session exists
        existing = db.execute(
            "SELECT session_id FROM session_contexts WHERE session_id = ?",
            (sid,)
        )

        if existing:
            # Update last activity
            db.execute(
                "UPDATE session_contexts SET last_activity = CURRENT_TIMESTAMP() WHERE session_id = ?",
                (sid,)
            )
            created = False
        else:
            # Create new session
            db.execute("""
                INSERT INTO session_contexts (session_id, user_id, org_id, max_tokens)
                VALUES (?, ?, ?, ?)
            """, (sid, user_id, org_id, max_tokens))
            created = True

        return json.dumps({
            "session_id": sid,
            "created": created,
            "max_tokens": max_tokens
        })

    @server.tool()
    async def add_to_working_memory(
        session_id: str,
        content: str,
        content_type: str,
        pinned: bool = False
    ) -> str:
        """Add an item to working memory."""

        item_id = str(uuid.uuid4())
        token_count = embedding_service.count_tokens(content)

        # Get next sequence number
        result = db.execute(
            "SELECT COALESCE(MAX(sequence_num), 0) + 1 FROM working_memory_items WHERE session_id = ?",
            (session_id,)
        )
        seq_num = result[0][0] if result else 1

        # Insert item
        db.execute("""
            INSERT INTO working_memory_items
            (item_id, session_id, user_id, content_type, content, token_count, pinned, sequence_num)
            SELECT ?, session_id, user_id, ?, ?, ?, ?, ?
            FROM session_contexts WHERE session_id = ?
        """, (item_id, content_type, content, token_count, pinned, seq_num, session_id))

        # Update session token count
        db.execute("""
            UPDATE session_contexts
            SET total_tokens = total_tokens + ?, last_activity = CURRENT_TIMESTAMP()
            WHERE session_id = ?
        """, (token_count, session_id))

        # TODO: Check if eviction needed and handle it

        return json.dumps({
            "item_id": item_id,
            "token_count": token_count,
            "sequence_num": seq_num
        })

    @server.tool()
    async def get_working_memory(
        session_id: str,
        token_budget: Optional[int] = None
    ) -> str:
        """Retrieve current working memory state."""

        # Get session info
        session = db.execute(
            "SELECT max_tokens, total_tokens FROM session_contexts WHERE session_id = ?",
            (session_id,)
        )

        if not session:
            return json.dumps({"error": "Session not found"})

        max_tokens, total_tokens = session[0]
        budget = token_budget or max_tokens

        # Get items ordered by relevance and recency
        items = db.execute("""
            SELECT item_id, content_type, content, token_count, pinned, relevance_score
            FROM working_memory_items
            WHERE session_id = ?
            ORDER BY pinned DESC, relevance_score DESC, sequence_num DESC
        """, (session_id,))

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
                    "pinned": item[4],
                    "relevance_score": item[5]
                })
                used_tokens += item_tokens

        return json.dumps({
            "items": result_items,
            "total_tokens": used_tokens,
            "truncated": used_tokens < total_tokens
        })

    @server.tool()
    async def clear_working_memory(
        session_id: str,
        checkpoint_first: bool = True
    ) -> str:
        """Clear working memory for a session."""

        # TODO: If checkpoint_first, save important items to long-term memory

        db.execute(
            "DELETE FROM working_memory_items WHERE session_id = ?",
            (session_id,)
        )

        db.execute(
            "UPDATE session_contexts SET total_tokens = 0 WHERE session_id = ?",
            (session_id,)
        )

        return json.dumps({"success": True})
```

### 4.3 Long-Term Memory Tools

```python
# src/tools/longterm_memory.py
from mcp.server import Server
from typing import Optional, List
import uuid
import json

from src.db.client import db
from src.llm.embeddings import embedding_service
from src.llm.ollama import ollama_service
from src.memory.taxonomy import validate_subtype

def register_longterm_memory_tools(server: Server):

    @server.tool()
    async def store_memory(
        user_id: str,
        content: str,
        memory_category: Optional[str] = None,
        memory_subtype: Optional[str] = None,
        importance: float = 0.5,
        entities: Optional[List[str]] = None,
        event_time: Optional[str] = None,
        metadata: Optional[str] = None  # JSON string
    ) -> str:
        """Store a memory in long-term storage."""

        memory_id = str(uuid.uuid4())

        # Auto-classify if category/subtype not provided
        if not memory_category or not memory_subtype:
            classification = ollama_service.classify_memory(content)
            memory_category = memory_category or classification.memory_category
            memory_subtype = memory_subtype or classification.memory_subtype
            importance = classification.importance if importance == 0.5 else importance
            entities = entities or classification.entities

        # Validate taxonomy
        if not validate_subtype(memory_category, memory_subtype):
            return json.dumps({
                "error": f"Invalid subtype '{memory_subtype}' for category '{memory_category}'"
            })

        # Extract entities if not provided
        if not entities:
            entities = ollama_service.extract_entities(content)

        # Generate embedding
        embedding = embedding_service.generate(content)

        # Check for similar existing memories
        # TODO: Implement similarity search once Firebolt vector syntax confirmed

        # Insert memory
        db.execute("""
            INSERT INTO long_term_memories (
                memory_id, user_id, memory_category, memory_subtype,
                content, embedding, entities, importance,
                event_time, metadata, is_temporal
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory_id, user_id, memory_category, memory_subtype,
            content, embedding, entities, importance,
            event_time, metadata, event_time is not None
        ))

        return json.dumps({
            "memory_id": memory_id,
            "memory_category": memory_category,
            "memory_subtype": memory_subtype,
            "entities_extracted": entities
        })

    @server.tool()
    async def recall_memories(
        user_id: str,
        query: str,
        memory_categories: Optional[List[str]] = None,
        memory_subtypes: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        limit: int = 10,
        min_similarity: float = 0.7
    ) -> str:
        """Recall relevant memories using semantic search."""

        # Generate query embedding
        query_embedding = embedding_service.generate(query)

        # Build query with Firebolt vector similarity
        # Uses VECTOR_COSINE_SIMILARITY: 1.0 = identical, -1.0 = opposite

        conditions = ["user_id = ?", "deleted_at IS NULL"]
        params = [user_id]

        if memory_categories:
            placeholders = ','.join(['?' for _ in memory_categories])
            conditions.append(f"memory_category IN ({placeholders})")
            params.extend(memory_categories)

        if memory_subtypes:
            placeholders = ','.join(['?' for _ in memory_subtypes])
            conditions.append(f"memory_subtype IN ({placeholders})")
            params.extend(memory_subtypes)

        where_clause = " AND ".join(conditions)

        # Firebolt vector similarity query
        # VECTOR_COSINE_SIMILARITY returns 1.0 for identical vectors
        results = db.execute(f"""
            SELECT
                memory_id,
                content,
                memory_category,
                memory_subtype,
                entities,
                importance,
                access_count,
                created_at,
                metadata,
                VECTOR_COSINE_SIMILARITY(embedding, ?) AS similarity
            FROM long_term_memories
            WHERE {where_clause}
              AND VECTOR_COSINE_SIMILARITY(embedding, ?) >= ?
            ORDER BY similarity DESC, importance DESC
            LIMIT ?
        """, (query_embedding, *params, query_embedding, min_similarity, limit))

        memories = []
        for row in results:
            memories.append({
                "memory_id": row[0],
                "content": row[1],
                "memory_category": row[2],
                "memory_subtype": row[3],
                "entities": row[4],
                "importance": row[5],
                "access_count": row[6],
                "created_at": str(row[7]),
                "metadata": row[8]
            })

        # Update access counts
        if memories:
            memory_ids = [m["memory_id"] for m in memories]
            for mid in memory_ids:
                db.execute("""
                    UPDATE long_term_memories
                    SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP()
                    WHERE memory_id = ?
                """, (mid,))

        return json.dumps({
            "memories": memories,
            "retrieval_breakdown": {
                "total_returned": len(memories),
                "query_tokens": embedding_service.count_tokens(query)
            }
        })

    @server.tool()
    async def forget_memory(
        memory_id: str,
        user_id: str,
        hard_delete: bool = False
    ) -> str:
        """Delete a memory (soft delete by default for GDPR compliance)."""

        if hard_delete:
            db.execute(
                "DELETE FROM long_term_memories WHERE memory_id = ? AND user_id = ?",
                (memory_id, user_id)
            )
        else:
            db.execute("""
                UPDATE long_term_memories
                SET deleted_at = CURRENT_TIMESTAMP()
                WHERE memory_id = ? AND user_id = ?
            """, (memory_id, user_id))

        return json.dumps({"success": True, "hard_deleted": hard_delete})
```

### 4.4 Smart Context Tool

```python
# src/tools/context.py
from mcp.server import Server
from typing import Optional, List, Dict
import json

from src.db.client import db
from src.llm.embeddings import embedding_service
from src.llm.ollama import ollama_service
from src.memory.taxonomy import get_retrieval_weights

def register_context_tools(server: Server):

    @server.tool()
    async def get_relevant_context(
        session_id: str,
        user_id: str,
        query: str,
        token_budget: int,
        query_intent: Optional[str] = None,
        focus_entities: Optional[List[str]] = None
    ) -> str:
        """
        Assemble optimal context from working + long-term memory.
        This is the primary "smart retrieval" tool.
        """

        # Detect intent if not provided
        if not query_intent:
            query_intent = ollama_service.detect_query_intent(query)

        # Get retrieval weights for this intent
        weights = get_retrieval_weights(query_intent)

        context_items = []
        total_tokens = 0

        # Phase 1: Get working memory items
        working_budget = int(token_budget * weights.get("working_memory", 0.35))

        working_items = db.execute("""
            SELECT item_id, content_type, content, token_count, relevance_score
            FROM working_memory_items
            WHERE session_id = ?
            ORDER BY pinned DESC, sequence_num DESC
        """, (session_id,))

        for item in working_items:
            if total_tokens + item[3] > working_budget:
                break
            context_items.append({
                "source": "working_memory",
                "content": item[2],
                "relevance_score": item[4],
                "token_count": item[3],
                "why_included": f"Recent {item[1]} from current session"
            })
            total_tokens += item[3]

        # Phase 2: Get long-term memories
        remaining_budget = token_budget - total_tokens
        query_embedding = embedding_service.generate(query)

        # Retrieve from each memory type based on weights
        ltm_results = []

        # TODO: Implement proper vector similarity search with Firebolt
        # For now, use importance + recency as proxy
        for weight_key, weight in weights.items():
            if weight_key == "working_memory":
                continue

            parts = weight_key.split(".")
            if len(parts) != 2:
                continue

            category, subtype = parts
            type_budget = int(remaining_budget * weight)

            if type_budget < 50:  # Skip if budget too small
                continue

            memories = db.execute("""
                SELECT memory_id, content, memory_category, memory_subtype,
                       entities, importance, created_at
                FROM long_term_memories
                WHERE user_id = ?
                  AND memory_category = ?
                  AND memory_subtype = ?
                  AND deleted_at IS NULL
                ORDER BY importance DESC, last_accessed DESC
                LIMIT 5
            """, (user_id, category, subtype))

            for mem in memories:
                token_count = embedding_service.count_tokens(mem[1])
                ltm_results.append({
                    "memory_id": mem[0],
                    "content": mem[1],
                    "memory_category": mem[2],
                    "memory_subtype": mem[3],
                    "entities": mem[4],
                    "token_count": token_count,
                    "importance": mem[5],
                    "weight": weight,
                    "score": mem[5] * weight  # Simple scoring
                })

        # Entity boost: increase score for memories matching focus entities
        if focus_entities:
            for item in ltm_results:
                item_entities = item.get("entities") or []
                matches = len(set(focus_entities) & set(item_entities))
                if matches > 0:
                    item["score"] *= (1 + 0.3 * matches)  # 30% boost per match

        # Sort by score and fill remaining budget
        ltm_results.sort(key=lambda x: x["score"], reverse=True)

        for item in ltm_results:
            if total_tokens + item["token_count"] > token_budget:
                continue
            context_items.append({
                "source": "long_term",
                "memory_category": item["memory_category"],
                "memory_subtype": item["memory_subtype"],
                "content": item["content"],
                "relevance_score": item["score"],
                "token_count": item["token_count"],
                "entities": item["entities"],
                "why_included": f"{item['memory_category']}.{item['memory_subtype']} memory (score: {item['score']:.2f})"
            })
            total_tokens += item["token_count"]

        return json.dumps({
            "context_items": context_items,
            "total_tokens": total_tokens,
            "budget_used_pct": round(total_tokens / token_budget * 100, 2),
            "detected_intent": query_intent,
            "retrieval_stats": {
                "working_memory_items": len([i for i in context_items if i["source"] == "working_memory"]),
                "long_term_items": len([i for i in context_items if i["source"] == "long_term"]),
                "entity_boost_applied": focus_entities is not None and len(focus_entities) > 0
            }
        })
```

---

## Phase 5: Testing & Validation (Days 9-11)

### 5.1 Unit Tests

```python
# tests/test_working_memory.py
import pytest
from src.tools.working_memory import *

@pytest.mark.asyncio
async def test_init_session_creates_new():
    result = await init_session(user_id="test_user")
    data = json.loads(result)
    assert data["created"] == True
    assert "session_id" in data

@pytest.mark.asyncio
async def test_add_and_get_working_memory():
    # Init session
    session = json.loads(await init_session(user_id="test_user"))
    session_id = session["session_id"]

    # Add item
    add_result = json.loads(await add_to_working_memory(
        session_id=session_id,
        content="Test message content",
        content_type="message"
    ))
    assert add_result["token_count"] > 0

    # Get working memory
    get_result = json.loads(await get_working_memory(session_id=session_id))
    assert len(get_result["items"]) == 1
    assert get_result["items"][0]["content"] == "Test message content"
```

### 5.2 Integration Tests

```python
# tests/test_integration.py
import pytest
from src.tools.working_memory import init_session, add_to_working_memory
from src.tools.longterm_memory import store_memory, recall_memories
from src.tools.context import get_relevant_context

@pytest.mark.asyncio
async def test_full_memory_flow():
    user_id = "integration_test_user"

    # 1. Create session
    session = json.loads(await init_session(user_id=user_id))
    session_id = session["session_id"]

    # 2. Store some long-term memories
    await store_memory(
        user_id=user_id,
        content="The users table has columns: id, email, password_hash, created_at",
        memory_category="semantic",
        memory_subtype="entity",
        entities=["table:users"]
    )

    await store_memory(
        user_id=user_id,
        content="To add a database migration, run: alembic revision --autogenerate",
        memory_category="procedural",
        memory_subtype="workflow"
    )

    # 3. Add to working memory
    await add_to_working_memory(
        session_id=session_id,
        content="User asked about modifying the users table",
        content_type="message"
    )

    # 4. Get relevant context
    context = json.loads(await get_relevant_context(
        session_id=session_id,
        user_id=user_id,
        query="How do I add a new field to the users table?",
        token_budget=2000,
        focus_entities=["table:users"]
    ))

    assert context["total_tokens"] > 0
    assert len(context["context_items"]) > 0
    assert context["detected_intent"] == "how_to"
```

### 5.3 Manual Testing with Claude Desktop

Create MCP configuration for Claude Desktop:

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "firebolt-memory": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/fml-server",
      "env": {
        "FIREBOLT_CLIENT_ID": "...",
        "FIREBOLT_CLIENT_SECRET": "...",
        "OPENAI_API_KEY": "..."
      }
    }
  }
}
```

---

## Phase 6: Documentation & Demo (Days 11-14)

### 6.1 README

Create comprehensive README with:
- Installation instructions
- Configuration guide
- Usage examples
- MCP tool documentation
- Troubleshooting

### 6.2 Demo Script

```python
# scripts/demo.py
"""
Interactive demo of FML capabilities.
"""
import asyncio
from src.tools.working_memory import init_session, add_to_working_memory
from src.tools.longterm_memory import store_memory, recall_memories
from src.tools.context import get_relevant_context

async def run_demo():
    print("=== Firebolt Memory Layer Demo ===\n")

    user_id = "demo_user"

    # Initialize session
    print("1. Initializing session...")
    session = json.loads(await init_session(user_id=user_id))
    print(f"   Session created: {session['session_id']}\n")

    # Store some memories
    print("2. Storing memories...")

    memories_to_store = [
        {
            "content": "User's name is Sarah and she is a senior backend engineer",
            "category": "semantic",
            "subtype": "user"
        },
        {
            "content": "Project uses Python 3.11 with FastAPI and SQLAlchemy",
            "category": "semantic",
            "subtype": "project"
        },
        {
            "content": "Decided to use PostgreSQL for the database because of JSONB support",
            "category": "episodic",
            "subtype": "decision"
        },
        {
            "content": "User prefers detailed explanations with code examples",
            "category": "preference",
            "subtype": "communication"
        }
    ]

    for mem in memories_to_store:
        result = await store_memory(
            user_id=user_id,
            content=mem["content"],
            memory_category=mem["category"],
            memory_subtype=mem["subtype"]
        )
        print(f"   Stored: {mem['content'][:50]}...")

    print("\n3. Retrieving context for a query...")
    query = "What database are we using and why?"

    context = json.loads(await get_relevant_context(
        session_id=session['session_id'],
        user_id=user_id,
        query=query,
        token_budget=1000
    ))

    print(f"   Query: {query}")
    print(f"   Detected intent: {context['detected_intent']}")
    print(f"   Retrieved {len(context['context_items'])} items:")

    for item in context['context_items']:
        print(f"   - [{item.get('memory_category', 'working')}.{item.get('memory_subtype', 'memory')}] {item['content'][:60]}...")

    print("\n=== Demo Complete ===")

if __name__ == "__main__":
    asyncio.run(run_demo())
```

---

## Timeline Summary

| Phase | Days | Deliverables |
|-------|------|-------------|
| **1. Environment Setup** | 1-2 | Dev environment, Firebolt/Ollama/OpenAI configured |
| **2. Database Schema** | 2-3 | Tables created, migration scripts |
| **3. Core Services** | 3-6 | DB client, embedding service, Ollama service, taxonomy |
| **4. MCP Tools** | 6-9 | All MCP tools implemented |
| **5. Testing** | 9-11 | Unit tests, integration tests, manual testing |
| **6. Documentation** | 11-14 | README, demo script, usage examples |

---

## Immediate Next Steps

1. ~~**Confirm Firebolt vector syntax**~~ ✅ Done:
   - Vector column: `ARRAY(REAL)`
   - Similarity: `VECTOR_COSINE_SIMILARITY(a, b)` → 1.0 = identical
   - Distance: `VECTOR_COSINE_DISTANCE(a, b)` → 0.0 = identical

2. **Set up Firebolt account** — Create database and engine

3. **Install Ollama + Mistral** — `brew install ollama && ollama pull mistral:7b`

4. **Create project skeleton** — Initialize repo with structure above

5. **Get API keys** — OpenAI key for embeddings, Firebolt credentials

---

## Open Items / Risks

| Item | Risk Level | Mitigation |
|------|------------|------------|
| Firebolt vector syntax | ✅ Resolved | Using `ARRAY(REAL)` + `VECTOR_COSINE_SIMILARITY()` |
| Ollama performance on laptop | Low | 24GB RAM handles Mistral 7B easily |
| Embedding costs (OpenAI) | Low | Caching, batching |
| MCP protocol complexity | Low | Use existing MCP libraries |

---

## Success Criteria for Prototype

- [ ] Can initialize a session and add/retrieve working memory
- [ ] Can store memories with auto-classification (via Ollama)
- [ ] Can recall memories using semantic similarity
- [ ] Can assemble context with intelligent retrieval
- [ ] Works with Claude Desktop via MCP
- [ ] Sub-500ms latency for most operations
- [ ] Demo script runs successfully end-to-end
