# Local Agent Memory Layer (LAML)

**Persistent memory for AI agents — plus built-in token efficiency for every interaction.**

Local agent memory is [Relate](https://relatedb.ai): learned facts are a connected graph, queried with Cypher. Do not use a local Firebolt Core instance as the semantic layer. See [AGENTS.md](AGENTS.md).

LAML, in `laml/`, is the token-efficiency layer (and an optional older vector memory server). It **natively embeds [Headroom](https://github.com/chopratejas/headroom) and [RTK](https://github.com/rtk-ai/rtk)** so memory responses, shell commands, and other MCP tool output can be **40–90%** smaller. Optional LAML vector backends are Turbopuffer, Elasticsearch, ClickHouse, or Firebolt cloud. Local Firebolt Core is not one of them.

## Credits

**Core Author:** [John Tuite](https://github.com/tuitejc-firebolt) - The FML MCP server architecture and implementation is John's work. This project builds upon his foundational design for intelligent memory management in LLM agents.

---

## What This Does

### Memory (core)

- **Working Memory**: Session-scoped context that persists during a conversation
- **Long-Term Memory**: Vector-indexed persistent storage with semantic search
- **Auto-Classification**: Memories are automatically categorized (episodic, semantic, procedural, preference)
- **Semantic Recall**: Find relevant memories based on meaning, not just keywords
- **Local memory**: Relate on this Mac (`~/.relate/memory`), not Firebolt Core

### Token efficiency (embedded — new)

LAML is a **memory layer and a token optimization layer** in one install:

| Layer | Tool | What gets smaller |
|-------|------|-------------------|
| LAML MCP responses | **Headroom** (in-server) | `recall_memories`, `get_working_memory`, stats JSON — often **40–60%+** on large recalls |
| Shell commands | **RTK** (Cursor/Claude hooks) | `git`, tests, lint, `docker`, `grep` — typically **60–90%** |
| Other MCP tools | **Headroom MCP** | Tool results from Firebolt, Cloudflare, custom servers |
| All agents | `laml token-tools setup` | One command wires Cursor + weekly updates |

Validated example: `recall_memories` compressed **641 → 347 tokens** (~46% saved) while preserving retrievable content via Headroom CCR.

→ Full guide: [laml/laml-server/docs/TOKEN_EFFICIENCY.md](laml/laml-server/docs/TOKEN_EFFICIENCY.md)

---

## Automatic memory behavior (out of the box)

This repo includes **`.cursorrules`** at the root so that when you open it in Cursor with the **laml** MCP server configured, the AI will **automatically**:

- **Start or resume a session** at the beginning of every conversation (`init_session`)
- **Load relevant long-term context** before answering (`recall_memories`)
- **Update working memory** after each substantive exchange (`add_to_working_memory`) — no need to ask
- **Promote important items to long-term memory** at milestones (`checkpoint_working_memory`, `store_memory`)

You get high-value, high-impact memory behavior in **every session** (new or existing projects) as soon as you add the LAML MCP server to Cursor. No extra setup or manual prompting required.

---

## Quick Start (Recommended)

For the fastest setup, use the bootstrap script after cloning this fork:

```bash
# Clone the repository (your fork)
git clone git@github.com:johnkennedy-cmyk/local-agent-memory-layer.git
cd local-agent-memory-layer

# Ensure Firebolt Core and Ollama are running first (see Prerequisites below)

# Run the bootstrap script - does everything automatically
cd laml/laml-server
./scripts/bootstrap.sh
```

The bootstrap script will:
- Set up Python virtual environment and dependencies (**includes Headroom**)
- Create database schema and tables
- **Seed core memories** (security rules, workflows, troubleshooting guides)
- Configure Cursor IDE with LAML rules, MCP settings, **RTK hooks, and Headroom**
- Schedule **weekly RTK/Headroom updates** (macOS launchd)
- Set up pre-commit security hooks

After bootstrap completes, **restart Cursor**, enable **laml** and **headroom** in Settings → Tools & MCP, then:

```bash
cd laml/laml-server && source .venv/bin/activate
laml token-tools status   # confirm RTK + Headroom
```

---

## Manual Setup Guide

If you prefer manual setup or the bootstrap script doesn't work for your environment:

### Prerequisites

You need:
- **macOS** (tested on macOS 15.x)
- **Docker Desktop** installed and running
- **Python 3.10+** (3.14 recommended)
- **Homebrew** for package management
- **Cursor IDE** (or any MCP-compatible client)

### Step 1: Install Dependencies

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python (if needed)
brew install python@3.14

# Install Ollama (local LLM)
brew install ollama

# Start Ollama and pull required models
ollama serve  # Run in a separate terminal, keep it running
ollama pull llama3:8b        # For classification
ollama pull nomic-embed-text  # For embeddings (768 dimensions)
```

### Step 2: Install Relate (local memory)

Local memory is Relate. The official installer checks the release signature and SHA-256, then installs the `relate` binary to `~/.local/bin`:

```bash
curl -sSfL https://relatedb.ai/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
relate --version
relate skill install
```

On this Mac the shared store is the directory `~/.relate/memory`, served on loopback by LaunchAgent `ai.relatedb.agent-memory` (MCP `http://127.0.0.1:8399/mcp`, Bolt `bolt://127.0.0.1:7687`, HTTP Query API port `7474`). Connection details and the graph model are in [AGENTS.md](AGENTS.md). Do not install or start Firebolt Core for memory.

The LAML server can still use a cloud vector backend. Turbopuffer is the one configured and tested in this repo. Set `LAML_VECTOR_BACKEND=turbopuffer` when you want that server. It is not a substitute for the Relate graph.

### Step 3: Clone and Set Up LAML

```bash
# Clone this repository (your fork)
git clone git@github.com:johnkennedy-cmyk/local-agent-memory-layer.git
cd local-agent-memory-layer

# Create Python virtual environment
cd laml/laml-server
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Step 4: Configure Environment

```bash
# Copy example config
cp config/env.example .env

# Edit .env with your settings
nano .env
```

**Local agent memory does not use this file.** Relate is configured in [AGENTS.md](AGENTS.md). If you still run the optional LAML vector server, point it at a cloud backend (`LAML_VECTOR_BACKEND=turbopuffer`), not at Firebolt Core:

```env
# Do not set FIREBOLT_USE_CORE=true. Local Firebolt Core is not the semantic layer.
FIREBOLT_USE_CORE=false
LAML_VECTOR_BACKEND=turbopuffer

# Ollama (Local LLM - runs at localhost:11434)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3:8b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_EMBEDDING_DIMENSIONS=768

# Optional: OpenAI (only if you want to use OpenAI embeddings instead)
# OPENAI_API_KEY=your-key-here
```

### Step 5: Optional LAML vector schema

Local memory is the Relate directory from Step 2 (`~/.relate/memory`). Skip this step for that store. The commands below initialize tables only when you run the optional LAML vector server.

```bash
# Ensure virtual environment is active
source .venv/bin/activate

# Create database and tables in Firebolt Core
python scripts/migrate.py
```

This creates (for the Firebolt Core backend):
- `laml` database
- `session_contexts` table (working memory sessions)
- `working_memory_items` table (active context)
- `long_term_memories` table (persistent memories with vector index)
- `memory_access_log` table (analytics)
- `idx_memories_embedding` HNSW vector index (768 dimensions for Ollama)

### Step 6: Seed Core Memories (Recommended)

Pre-load essential memories for security rules, workflows, and troubleshooting:

```bash
# Seed core memories for optimal experience
python scripts/seed_core_memories.py
```

This creates foundational memories that help FML:
- Enforce security rules consistently
- Follow proper session workflows
- Troubleshoot common issues
- Understand FML architecture

### Step 7: Test the Setup

```bash
# Test all connections
python scripts/test_connections.py

# Test the MCP tools
python scripts/test_tools.py

# Test security validation
python scripts/test_security.py
```

### Step 8: Configure MCP Client to Use LAML

LAML works with any MCP-compatible client. See **[Platform Setup Guide](laml/laml-server/docs/MCP_PLATFORM_SETUP.md)** for detailed instructions for:
- **Claude Code** (Anthropic)
- **Google Gemini** / Antigravity Codes
- **Cursor IDE** (shown below)

#### For Cursor IDE

Create or edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "laml": {
      "command": "/path/to/local-agent-memory-layer/laml/laml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/local-agent-memory-layer/laml/laml-server",
      "env": {
        "PYTHONPATH": "/path/to/local-agent-memory-layer/laml/laml-server"
      }
    }
  }
}
```

**Important**: Replace `/path/to/` with the actual path where you cloned the repo.

Example for typical setup:
```json
{
  "mcpServers": {
    "laml": {
      "command": "/Users/YOUR_USERNAME/DevelopmentArea/local-agent-memory-layer/laml/laml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/Users/YOUR_USERNAME/DevelopmentArea/local-agent-memory-layer/laml/laml-server",
      "env": {
        "PYTHONPATH": "/Users/YOUR_USERNAME/DevelopmentArea/local-agent-memory-layer/laml/laml-server"
      }
    }
  }
}
```

Configuration templates are available in `laml/laml-server/config/` directory.

### Step 9: Add Global Cursor Rules

Copy `cursor-rules/laml-memory.mdc` to `~/.cursor/rules/laml-memory.mdc`. This tells Cursor agents on this Mac to use the Relate graph, not local Firebolt.

### Step 10: Restart Cursor

After adding the MCP config and rules, restart Cursor completely (Cmd+Q, then reopen).

---

## Verification

After setup, test in a new Cursor chat:

1. The agent should automatically call `init_session` at the start
2. The agent should call `recall_memories` based on your query
3. You can explicitly ask: "What do you remember about me?" to test recall

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Cursor IDE (MCP Client)                                    │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol (stdio)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  LAML MCP Server (Python)                                   │
│  ├── Working Memory Tools (5 tools)                         │
│  ├── Long-Term Memory Tools (5 tools)                       │
│  ├── Context Assembly Tools (2 tools)                       │
│  └── Stats/Analytics Tools (3 tools)                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌──────────┴──────────┐
          ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│  Local Vector   │   │     Ollama      │
│  Database       │   │  (localhost:    │
│  (e.g. Firebolt │   │   11434)        │
│   Core, Elastic)│   │  - Embeddings   │
│  - Vector Index │   │  - Classification│
└─────────────────┘   └─────────────────┘
```

---

## MCP Tools Available

### Working Memory (5 tools)
| Tool | Description |
|------|-------------|
| `init_session` | Initialize or resume a memory session |
| `add_to_working_memory` | Add item to working memory |
| `get_working_memory` | Retrieve current working memory state |
| `update_working_memory_item` | Update item properties (pinned, relevance) |
| `clear_working_memory` | Clear working memory for a session |

### Long-Term Memory (5 tools)
| Tool | Description |
|------|-------------|
| `store_memory` | Store a memory with auto-classification |
| `recall_memories` | Semantic search for relevant memories |
| `update_memory` | Update an existing memory |
| `forget_memory` | Delete a memory (soft delete) |
| `forget_all_user_memories` | GDPR-compliant full deletion |

### Context Assembly (2 tools)
| Tool | Description |
|------|-------------|
| `get_relevant_context` | Assemble optimal context from all sources |
| `checkpoint_working_memory` | Promote working memory to long-term |

### Stats (3 tools)
| Tool | Description |
|------|-------------|
| `get_laml_stats` | Server statistics and metrics |
| `get_recent_calls` | Recent API call history |
| `get_memory_analytics` | Memory distribution analytics |

---

## Memory Categories

Memories are auto-classified into human-aligned categories:

| Category | Use For | Subtypes |
|----------|---------|----------|
| `episodic` | Events, decisions, outcomes | decision, outcome, interaction, milestone |
| `semantic` | Facts, knowledge, entities | entity, concept, relationship, domain |
| `procedural` | Workflows, patterns, how-to | workflow, pattern, command, troubleshooting |
| `preference` | User preferences, style | coding_style, communication, tool_preference, constraint |

---

## Troubleshooting

### Relate memory not responding
1. Check the writer: `lsof -nP -iTCP:8399 -sTCP:LISTEN` (MCP), `7687` (Bolt), `7474` (HTTP Query API).
2. LaunchAgent label: `ai.relatedb.agent-memory`. Logs: `~/.relate/serve.err` (mode 0600; it can contain the local auth token — do not paste it into chat).
3. A second writable open of `~/.relate/memory` exits 5 while that server is running. Read with `--read-only=live`, or query through MCP.
4. Restart Cursor completely (Cmd+Q) after changing `~/.cursor/mcp.json`.

### Dashboard showing incorrect/stale data
The HTTP API server (used by the dashboard) doesn't auto-reload when code changes. If you see:
- Incorrect "All-Time Calls" counts (e.g., showing 4 instead of hundreds)
- Missing data in sections (Recent LLM Calls empty, Memory Data Size showing 0)
- Features not working that should be implemented

**Solution:** Check if the server needs a restart:
```bash
# Check server sync status
curl http://localhost:8082/api/version

# If "needs_restart": true, restart the server:
pkill -f "python.*http_api"
cd laml/laml-server
source .venv/bin/activate
PYTHONPATH=. python -m src.http_api &
```

The dashboard will also show a yellow warning banner when the server is running stale code, with the restart command included.

**Why this happens:** The `http_api` server is a separate Python process that loads code once at startup. Unlike the MCP server (which restarts with each Cursor session), the HTTP API runs continuously. After code changes, the running server still has the old code in memory until manually restarted.

### "tuple index out of range" error
This usually means the database is empty or the vector index doesn't exist. Run:
```bash
python scripts/migrate.py
```

### Vector dimension mismatch
Ensure you're using Ollama's `nomic-embed-text` (768 dimensions). If switching from OpenAI (1536 dimensions), you need to:
1. Drop the existing vector index
2. Recreate with `dimension = 768`
3. Re-embed all existing memories

### Transaction conflicts
Firebolt Core only allows one write transaction at a time. The FML server uses a mutex to serialize requests, but if you see transaction errors, wait a moment and retry.

---

## Dashboard (Optional)

LAML includes a React dashboard for monitoring:

```bash
cd laml/dashboard
npm install
npm run dev
```

Also start the HTTP API:
```bash
cd laml/laml-server
source .venv/bin/activate
python -m src.http_api
```

Dashboard runs at `http://localhost:5174`

The dashboard is optional and is not the local memory store. Local memory is Relate (see below).

---

## Local memory (Relate)

Agents on this Mac share one Relate store, outside this checkout:

| | |
|--|--|
| Store | `~/.relate/memory` (directory) |
| MCP | `http://127.0.0.1:8399/mcp` |
| Bolt | `bolt://127.0.0.1:7687` |
| HTTP Query API | `POST http://127.0.0.1:7474/db/neo4j/query/v2` |
| Tools | `get_schema`, `read_cypher`, `write_cypher` |
| Auth | HTTP Basic user `relate`. Password file `~/.relate/memory.auth-token` (mode 0600). Put the header only in `~/.cursor/mcp.json`, never in git. |

```json
{
  "mcpServers": {
    "relate": {
      "url": "http://127.0.0.1:8399/mcp"
    }
  }
}
```

Add the Basic header locally. The `relate` skill (`relate skill install`) is installed for Cursor, Claude Code, Gemini CLI, and Antigravity on this Mac. Cursor rules: copy `cursor-rules/laml-memory.mdc` to `~/.cursor/rules/laml-memory.mdc`.

Do not add a Firebolt MCP server, and do not point memory at `localhost:3473`.

---

## Project Structure

```
local-agent-memory-layer/
├── laml/
│   ├── fml-server/              # Core MCP server (Python)
│   │   ├── src/
│   │   │   ├── server.py        # MCP server entry point
│   │   │   ├── config.py        # Configuration management
│   │   │   ├── db/              # Database client
│   │   │   ├── llm/             # Ollama/OpenAI integration
│   │   │   ├── memory/          # Memory taxonomy
│   │   │   └── tools/           # MCP tool implementations
│   │   ├── scripts/
│   │   │   ├── schema.sql       # Database schema
│   │   │   └── migrate.py       # Migration script
│   │   └── config/
│   │       └── env.example      # Example environment config
│   └── dashboard/               # React monitoring dashboard
├── cursor-rules/
│   └── laml-memory.mdc          # Cursor rule: Relate graph memory
├── AGENTS.md                    # Relate connection notes for agents
└── README.md                    # This file
```

---

## Security

LAML implements multiple layers of security to protect sensitive data.

### Built-in Secret Detection

LAML includes **programmatic security validation** that automatically blocks storage of sensitive data. When you attempt to store content containing secrets, the operation is rejected with a detailed error.

**Detected patterns include:**

| Category | Examples |
|----------|----------|
| **API Keys** | OpenAI (`sk-*`), GitHub (`ghp_*`), AWS (`AKIA*`), Google (`AIza*`), Anthropic, Slack, Stripe |
| **Tokens** | Bearer tokens, JWT tokens, Authorization headers |
| **Passwords** | Password assignments, database connection strings, passwords in URLs |
| **Private Keys** | RSA, PGP, and generic private key blocks |
| **Secrets** | Generic secret/token assignments, `.env`-style content |

**Example rejection:**
```json
{
  "error": "SECURITY_VIOLATION",
  "message": "SECURITY BLOCK: Content contains 1 critical security violation(s). Detected: OpenAI API Key.",
  "hint": "Sensitive data like API keys, passwords, and tokens should not be stored in memory."
}
```

### Security Best Practices

When using LAML, follow these guidelines:

1. **Never store actual credentials** - Store descriptions or references instead
   - ❌ `"The API key is sk-abc123..."`
   - ✅ `"OpenAI API key is stored in .env as OPENAI_API_KEY"`

2. **Use environment variables** - All secrets should be in `.env` files
   - `.env` files are git-ignored by default
   - Use `.env.example` for templates with placeholder values

3. **Local-first architecture** - When using Firebolt Core + Ollama:
   - No data leaves your machine
   - No cloud API calls required
   - Full control over your data

### Pre-commit Hooks

The repository includes pre-commit hooks for additional security:

```bash
# Install pre-commit hooks
cd laml/laml-server
pip install pre-commit detect-secrets
pre-commit install

# Run security scan manually
pre-commit run --all-files

# Scan for secrets
detect-secrets scan .
```

**Configured hooks:**
- `detect-secrets` - Scans for hardcoded credentials
- `detect-private-key` - Prevents committing private keys
- `check-env-files` - Blocks `.env` file commits

### Running Security Tests

Verify the security validation is working:

```bash
cd laml/laml-server
source .venv/bin/activate
python scripts/test_security.py
```

### Reporting Security Issues

If you discover a security vulnerability, please:
1. **Do not** open a public issue
2. Email the maintainer directly with details
3. Allow time for a fix before public disclosure

---

## License

Apache 2.0
