# Local Agent Memory Layer (LAML) Server

An MCP server that provides intelligent memory management for LLM applications, using a local vector database as the data layer. Working memory/session state uses **Firebolt Core**, and long-term memory/vector search can use **Firebolt** (default), **Elasticsearch**, or **ClickHouse**.

## Features

- **Working Memory**: Fast, session-scoped storage for active context
- **Long-Term Memory**: Persistent vector-enabled storage with semantic search
- **Human-Aligned Taxonomy**: Memory types modeled after human cognition
  - Episodic (events, decisions, outcomes)
  - Semantic (facts, knowledge, entities)
  - Procedural (workflows, patterns)
  - Preference (communication style, tool preferences)
- **Smart Retrieval**: Query-intent-aware context assembly

## Quick Start

### Prerequisites

- Python 3.10+
- **Firebolt Core** for working memory/session state
- A vector backend for long-term memory:
  - **Firebolt Core / Firebolt Cloud** (default)
  - **Elasticsearch** (see [Elastic backend](docs/ELASTIC_VECTOR_BACKEND.md))
  - **ClickHouse** (see [ClickHouse backend](docs/CLICKHOUSE_VECTOR_BACKEND.md))
- OpenAI API key (for embeddings), or a compatible local embedding model
- Ollama installed locally (for classification and/or embeddings)

### Setup

1. **Clone and install dependencies:**
   ```bash
   cd laml-server
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Install and start Ollama:**
   ```bash
   brew install ollama
   ollama serve  # In a separate terminal
   ollama pull mistral:7b
   ```

4. **Test connections (Firebolt, vector backend, Ollama):**
   ```bash
   python scripts/test_connections.py
   ```

5. **Run database migrations (Firebolt schemas):**
   ```bash
   python scripts/migrate.py
   ```

6. **Start the MCP server:**
   ```bash
   python -m src.server
   ```

## Using with MCP Clients

LAML works with any MCP-compatible client. See **[Platform Setup Guide](docs/MCP_PLATFORM_SETUP.md)** for detailed instructions for:
- **Claude Code** (Anthropic)
- **Google Gemini** / Antigravity Codes
- **Cursor IDE** (current setup)

### Quick Setup for Cursor

Add to your Cursor settings (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "laml": {
      "command": "/path/to/laml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/laml-server",
      "env": {
        "PYTHONPATH": "/path/to/laml-server"
      }
    }
  }
}
```

Configuration templates are available in `config/` directory:
- `cursor-mcp.json.template` - For Cursor IDE
- `claude-code-mcp.json.template` - For Claude Code
- `google-gemini-mcp.json.template` - For Google Gemini

## Configuration

Environment variables (in `.env`):

| Variable | Description |
|----------|-------------|
| `LAML_VECTOR_BACKEND` | `firebolt` (default), `elastic`, or `clickhouse` |
| `OPENAI_API_KEY` | OpenAI API key for embeddings (if using OpenAI) |
| `FIREBOLT_ACCOUNT_NAME` | Firebolt account name (for Firebolt backend) |
| `FIREBOLT_CLIENT_ID` | Firebolt client ID (for Firebolt backend) |
| `FIREBOLT_CLIENT_SECRET` | Firebolt client secret (for Firebolt backend) |
| `FIREBOLT_DATABASE` | Firebolt database name (for Firebolt backend & working memory) |
| `FIREBOLT_ENGINE` | Firebolt engine name (for Firebolt backend & working memory) |
| `ELASTICSEARCH_URL` | Elasticsearch URL (for Elastic vector backend) |
| `ELASTICSEARCH_INDEX` | Elasticsearch index name (for Elastic vector backend) |
| `CLICKHOUSE_HOST` | ClickHouse host (for ClickHouse vector backend) |
| `CLICKHOUSE_PORT` | ClickHouse HTTP port (for ClickHouse vector backend, default `8123`) |
| `CLICKHOUSE_DATABASE` | ClickHouse database name (for ClickHouse vector backend) |
| `CLICKHOUSE_TABLE` | ClickHouse table name (for ClickHouse vector backend) |
| `CLICKHOUSE_USER` | ClickHouse user (for ClickHouse vector backend) |
| `CLICKHOUSE_PASSWORD` | ClickHouse password (for ClickHouse vector backend) |
| `CLICKHOUSE_EMBEDDING_DIMENSIONS` | Embedding dimension (e.g. `768`) for ClickHouse backend |
| `OLLAMA_HOST` | Ollama server URL (default: http://localhost:11434) |
| `OLLAMA_MODEL` | Ollama model to use (default: mistral:7b) |

### Choose your vector backend

After completing the base setup above, pick one of these quick paths:

- **Firebolt (default, simplest)**
  - Ensure Firebolt Core (or Firebolt Cloud) is running **before starting any MCP clients**:
    ```bash
    curl http://localhost:3473/?output_format=TabSeparated -d "SELECT 1"
    # Should return: 1
    ```
  - In `.env`, set `LAML_VECTOR_BACKEND=firebolt` and fill the `FIREBOLT_*` variables.
  - Run Firebolt migrations:
    ```bash
    python scripts/migrate.py
    ```
  - Start the server:
    ```bash
    python -m src.server
    ```

- **Elasticsearch**
  - See **[Elastic backend](docs/ELASTIC_VECTOR_BACKEND.md)** for full details.
  - Typical local setup:
    ```bash
    # From laml-server/
    docker compose -f docker-compose.elastic.yml up -d
    # Optional quick health check (expects 200):
    curl http://localhost:9200
    python scripts/init_elastic.py
    ```
  - In `.env`, set:
    ```bash
    LAML_VECTOR_BACKEND=elastic
    ELASTICSEARCH_URL=http://localhost:9200
    ELASTICSEARCH_INDEX=laml-long-term-memories
    ```
  - Then start the server:
    ```bash
    python -m src.server
    ```

- **ClickHouse**
  - See **[ClickHouse backend](docs/CLICKHOUSE_VECTOR_BACKEND.md)** for full details.
  - Typical local setup:
    ```bash
    # From laml-server/
    docker compose -f docker-compose.clickhouse.yml up -d
    # Wait until healthy before configuring any ClickHouse MCP:
    curl http://localhost:8123/ping
    # Should return: Ok.
    python scripts/init_clickhouse.py
    ```
  - In `.env`, set:
    ```bash
    LAML_VECTOR_BACKEND=clickhouse
    CLICKHOUSE_HOST=localhost
    CLICKHOUSE_PORT=8123
    CLICKHOUSE_DATABASE=laml
    CLICKHOUSE_TABLE=long_term_memories
    CLICKHOUSE_USER=default
    CLICKHOUSE_PASSWORD=
    CLICKHOUSE_EMBEDDING_DIMENSIONS=768
    ```
  - Then start the server:
    ```bash
    python -m src.server
    ```

## MCP Tools

### Working Memory (5 tools)
- `init_session` - Initialize or resume a memory session
- `add_to_working_memory` - Add item to working memory with auto-eviction
- `get_working_memory` - Retrieve current working memory state
- `update_working_memory_item` - Update item properties (pinned, relevance)
- `clear_working_memory` - Clear working memory for a session

### Long-Term Memory (5 tools)
- `store_memory` - Store a memory with auto-classification via Ollama
- `recall_memories` - Recall relevant memories using semantic search
- `update_memory` - Update an existing memory
- `forget_memory` - Delete a memory (soft delete by default)
- `forget_all_user_memories` - GDPR-compliant full user data deletion

### Smart Context (2 tools)
- `get_relevant_context` - Assemble optimal context from all memory sources
- `checkpoint_working_memory` - Promote working memory items to long-term storage

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  MCP Client (Cursor, Claude Desktop, etc.)              │
└─────────────────────┬───────────────────────────────────┘
                      │ MCP Protocol
                      ▼
┌─────────────────────────────────────────────────────────┐
│  LAML MCP Server                                        │
│  ├── Working Memory Manager                             │
│  ├── Long-Term Memory Manager                           │
│  ├── Embedding Service (OpenAI)                         │
│  └── Classification Service (Ollama)                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Firebolt                                               │
│  ├── session_contexts (working memory)                  │
│  ├── working_memory_items                               │
│  ├── long_term_memories (with vector embeddings)        │
│  └── memory_access_log                                  │
└─────────────────────────────────────────────────────────┘
```

## License

MIT
