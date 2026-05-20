# Local Agent Memory Layer (LAML) Server

An MCP server for **intelligent memory** and **native token efficiency** in LLM agents.

LAML gives you persistent working + long-term memory with semantic search, and **embeds [Headroom](https://github.com/chopratejas/headroom) + [RTK](https://github.com/rtk-ai/rtk)** so you do not need separate token-optimization tooling:

- Every LAML tool response is **compressed before it reaches the agent** (Headroom, on by default).
- Shell commands in Cursor/Claude are **rewritten to RTK** for 60–90% smaller output (hooks).
- A **Headroom MCP server** entry compresses other MCP tool results (Firebolt, Cloudflare, etc.).
- **`laml token-tools`** CLI installs, configures, and weekly-updates both stacks.

Backends: **Firebolt** (default local), **Turbopuffer** (recommended cloud), **Elasticsearch**, or **ClickHouse** — one backend for sessions, working memory, and long-term vectors.

## Turbopuffer Cloud Option (Primary)

LAML supports **Turbopuffer** as a first-class backend for **all memory data paths**, and it is configured, tested, and known to work in this project:
- long-term memory + vector search
- sessions
- working memory

Quick switch in `.env`:

```bash
LAML_VECTOR_BACKEND=turbopuffer
TURBOPUFFER_API_KEY=...
TURBOPUFFER_REGION=gcp-us-central1
TURBOPUFFER_BASE_URL=https://gcp-us-central1.turbopuffer.com
TURBOPUFFER_LONG_TERM_NAMESPACE=laml_long_term_memories
TURBOPUFFER_SESSIONS_NAMESPACE=laml_sessions
TURBOPUFFER_WORKING_MEMORY_NAMESPACE=laml_working_memory
```

For a safe rollout from an existing Firebolt deployment, keep reads on Firebolt and mirror writes:

```bash
LAML_VECTOR_BACKEND=firebolt
LAML_DUAL_WRITE_BACKEND=turbopuffer
```

## Features

### Memory

- **Working Memory**: Fast, session-scoped storage for active context
- **Long-Term Memory**: Persistent vector-enabled storage with semantic search
- **Human-Aligned Taxonomy**: Episodic, semantic, procedural, preference
- **Smart Retrieval**: Query-intent-aware context assembly (`get_relevant_context`)
- **Quality tools**: Contradiction detection, decay, maintenance, analytics

### Token efficiency (embedded)

| Component | Package | Role |
|-----------|---------|------|
| In-server compression | `src/token_efficiency/` | Wraps every `@mcp.tool` output via Headroom |
| Agent setup | `laml token-tools setup` | RTK install, Cursor `mcp.json` + `hooks.json`, weekly launchd |
| Headroom MCP | `src.token_efficiency.headroom_mcp_entry` | `headroom_compress` / `headroom_retrieve` / `headroom_stats` |
| Metrics | `get_token_optimization_status`, `get_fml_stats` | Live compression savings per tool |

**Typical savings:** 40–60% on large `recall_memories` payloads; 60–90% on shell via RTK. Full docs: **[docs/TOKEN_EFFICIENCY.md](docs/TOKEN_EFFICIENCY.md)**.

## Quick Start

### Prerequisites

- Python 3.10+
- A single backend for all LAML data (sessions, working memory, long-term memory):
  - **Firebolt Core** (default local option)
  - **Turbopuffer** (primary cloud option, recommended cloud backend)
  - **Elasticsearch** (see [Elastic backend](docs/ELASTIC_VECTOR_BACKEND.md)) – Firebolt not required
  - **ClickHouse** (see [ClickHouse backend](docs/CLICKHOUSE_VECTOR_BACKEND.md)) – Firebolt not required
  - **Firebolt Cloud** (alternative cloud backend)
- OpenAI API key (for embeddings), or a compatible local embedding model
- Ollama installed locally (for classification and/or embeddings)

### Setup (recommended: bootstrap)

```bash
cd laml-server
./scripts/bootstrap.sh   # venv, DB, Cursor MCP, RTK + Headroom, weekly updates
```

Restart Cursor, enable **laml** and **headroom** MCP servers, then:

```bash
source .venv/bin/activate
laml token-tools status
```

### Manual setup

1. **Clone and install dependencies:**
   ```bash
   cd laml-server
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"    # includes headroom-ai[mcp]
   laml token-tools setup     # RTK + Cursor hooks + Headroom MCP
   ```

2. **Configure environment (local or cloud vector backend):**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials and choose your backend:
   # - Local default: LAML_VECTOR_BACKEND=firebolt
   # - Cloud recommended: LAML_VECTOR_BACKEND=turbopuffer
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

Use `config/cursor-mcp.json.template` (includes **laml** + **headroom**). Minimal example:

```json
{
  "mcpServers": {
    "laml": {
      "command": "/path/to/laml-server/.venv/bin/python3.11",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/laml-server",
      "env": {
        "PYTHONPATH": "/path/to/laml-server",
        "LAML_HEADROOM_COMPRESS": "true"
      }
    },
    "headroom": {
      "command": "/path/to/laml-server/.venv/bin/python3.11",
      "args": ["-m", "src.token_efficiency.headroom_mcp_entry"],
      "cwd": "/path/to/laml-server",
      "env": { "PYTHONPATH": "/path/to/laml-server" }
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
| `LAML_VECTOR_BACKEND` | `firebolt` (default), `elastic`, `clickhouse`, or `turbopuffer` |
| `LAML_DUAL_WRITE_BACKEND` | Optional secondary write backend during migrations (`firebolt`, `elastic`, `clickhouse`, `turbopuffer`) |
| `LAML_HEADROOM_COMPRESS` | `true` (default): compress MCP tool JSON via [Headroom](https://github.com/chopratejas/headroom) before responses reach the agent |
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

## Local-Only Workspace (Not Pushed)

Use `local-only/` for internal scripts, migration scratch work, and local state notes you do not want in GitHub.

- `local-only/` is git-ignored by default.
- `local-only/README.md` is tracked to document the convention.

### Choose your vector backend

After completing the base setup above, pick one of these quick paths:

- **Turbopuffer (primary cloud option)**
  - Set in `.env`:
    ```bash
    LAML_VECTOR_BACKEND=turbopuffer
    TURBOPUFFER_API_KEY=...
    TURBOPUFFER_REGION=gcp-us-central1
    TURBOPUFFER_BASE_URL=https://gcp-us-central1.turbopuffer.com
    TURBOPUFFER_LONG_TERM_NAMESPACE=laml_long_term_memories
    TURBOPUFFER_SESSIONS_NAMESPACE=laml_sessions
    TURBOPUFFER_WORKING_MEMORY_NAMESPACE=laml_working_memory
    ```
  - Start the server:
    ```bash
    python -m src.server
    ```
  - For rollout from existing Firebolt data, see **[Turbopuffer backend](docs/TURBOPUFFER_VECTOR_BACKEND.md)**.

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
  # If you already have a local Elasticsearch cluster (for example from elastic-start-local),
  # you can point LAML at that instead of starting the docker-compose profile.
  # Optional quick health check (expects JSON with cluster info):
  curl http://localhost:9200
  # Then create the LAML index with the proper dense_vector mapping:
  python scripts/init_elastic_index.py
    ```
  - In `.env`, set:
    ```bash
    LAML_VECTOR_BACKEND=elastic
    ELASTICSEARCH_URL=http://localhost:9200
  ELASTICSEARCH_INDEX=laml_long_term_memories
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

### Token efficiency (3 tools)
- `get_token_optimization_status` - RTK/Headroom versions, config, live compression metrics
- `setup_token_optimization` - Install/configure token tools for Cursor and other agents
- `update_token_optimization_tools` - Upgrade RTK (brew) and Headroom (pip)

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Agent (Cursor, Claude Code, …)                              │
├──────────────────────────────────────────────────────────────┤
│  Shell ──► RTK hook (~/.cursor/hooks.json) ──► compact output  │
│  LAML MCP ──► Headroom (in-server) ──► compact memory JSON   │
│  Other MCP ──► Headroom MCP ──► compress / retrieve          │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  LAML MCP Server (src/server.py)                             │
│  ├── token_efficiency/  (compression, agent_setup, CLI)      │
│  ├── Working + long-term memory tools                        │
│  ├── Embeddings + Ollama classification                      │
│  └── HTTP API + dashboard (optional)                         │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  Vector backend (Firebolt / Turbopuffer / Elastic / CH)    │
└──────────────────────────────────────────────────────────────┘
```

## CLI

| Command | Description |
|---------|-------------|
| `laml setup` | Cursor MCP + token tools |
| `laml token-tools setup` | Full RTK + Headroom install |
| `laml token-tools status` | Versions and compression metrics |
| `laml token-tools update` | Upgrade RTK and Headroom |

## License

MIT
