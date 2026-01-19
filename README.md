# Firebolt Memory Layer (FML)

An intelligent, persistent memory system for LLM agents using local Firebolt Core with HNSW vector search. Designed to give Cursor (and other MCP-compatible tools) long-term memory that persists across sessions.

## What This Does

- **Working Memory**: Session-scoped context that persists during a conversation
- **Long-Term Memory**: Vector-indexed persistent storage with semantic search
- **Auto-Classification**: Memories are automatically categorized (episodic, semantic, procedural, preference)
- **Semantic Recall**: Find relevant memories based on meaning, not just keywords
- **100% Local**: Runs entirely on your machine using Firebolt Core + Ollama (no cloud dependencies)

---

## New Laptop Setup Guide

Follow these steps to set up FML from scratch on a new machine.

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

### Step 2: Install Firebolt Core (Local Database)

Firebolt Core is a local version of Firebolt that runs in Docker.

```bash
# Install Firebolt Core using the official installer
bash <(curl -s https://get-core.firebolt.io/)

# Or if you have the manage script:
# cd firebolt-core-local && ./manage-firebolt.sh start

# Verify it's running (should return a response)
curl http://localhost:3473/?output_format=TabSeparated -d "SELECT 1"
```

Firebolt Core runs at `http://localhost:3473` by default.

### Step 3: Clone and Set Up FML

```bash
# Clone this repository
git clone git@github.com:johnkennedy-cmyk/Firebolt-Memory-Layer.git
cd Firebolt-Memory-Layer

# Create Python virtual environment
cd fml/fml-server
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

**For local-only setup (Firebolt Core + Ollama), use:**

```env
# Firebolt Core (Local)
FIREBOLT_USE_CORE=true
FIREBOLT_CORE_URL=http://localhost:3473
FIREBOLT_DATABASE=fml_memory

# Ollama (Local LLM - runs at localhost:11434)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3:8b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_EMBEDDING_DIMENSIONS=768

# Optional: OpenAI (only if you want to use OpenAI embeddings instead)
# OPENAI_API_KEY=your-key-here
```

### Step 5: Initialize Database Schema

```bash
# Ensure virtual environment is active
source .venv/bin/activate

# Create database and tables in Firebolt Core
python scripts/migrate.py
```

This creates:
- `fml_memory` database
- `session_contexts` table (working memory sessions)
- `working_memory_items` table (active context)
- `long_term_memories` table (persistent memories with vector index)
- `memory_access_log` table (analytics)
- `idx_memories_embedding` HNSW vector index (768 dimensions for Ollama)

### Step 6: Test the Setup

```bash
# Test all connections
python scripts/test_connections.py

# Test the MCP tools
python scripts/test_tools.py
```

### Step 7: Configure Cursor to Use FML

Create or edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "fml": {
      "command": "/path/to/Firebolt-Memory-Layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/Firebolt-Memory-Layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/path/to/Firebolt-Memory-Layer/fml/fml-server"
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
    "fml": {
      "command": "/Users/YOUR_USERNAME/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/Users/YOUR_USERNAME/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/Users/YOUR_USERNAME/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server"
      }
    }
  }
}
```

### Step 8: Add Global Cursor Rules

Create `~/.cursor/rules/fml-memory.mdc` with the content from `cursor-rules/fml-memory.mdc` in this repo. This tells all Cursor agents to use FML automatically.

### Step 9: Restart Cursor

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
│  FML MCP Server (Python)                                    │
│  ├── Working Memory Tools (5 tools)                         │
│  ├── Long-Term Memory Tools (5 tools)                       │
│  ├── Context Assembly Tools (2 tools)                       │
│  └── Stats/Analytics Tools (3 tools)                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌──────────┴──────────┐
          ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│  Firebolt Core  │   │     Ollama      │
│  (localhost:    │   │  (localhost:    │
│   3473)         │   │   11434)        │
│  - SQL Storage  │   │  - Embeddings   │
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
| `get_fml_stats` | Server statistics and metrics |
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

### FML not responding in Cursor
1. Check Firebolt Core is running: `curl http://localhost:3473/?output_format=TabSeparated -d "SELECT 1"`
2. Check Ollama is running: `curl http://localhost:11434/api/tags`
3. Check MCP config path is correct in `~/.cursor/mcp.json`
4. Restart Cursor completely (Cmd+Q)

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

FML includes a React dashboard for monitoring:

```bash
cd fml/dashboard
npm install
npm run dev
```

Also start the HTTP API:
```bash
cd fml/fml-server
source .venv/bin/activate
python -m src.http_api
```

Dashboard runs at `http://localhost:5174`

---

## Project Structure

```
Firebolt-Memory-Layer/
├── fml/
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
│   └── fml-memory.mdc           # Global Cursor rules for FML
├── firebolt-core-local/         # Firebolt Core management (if present)
└── README.md                    # This file
```

---

## Security Notes

- **Never commit `.env` files** - They contain credentials
- **No API keys in code** - All secrets via environment variables
- **Local-first** - No data leaves your machine when using Firebolt Core + Ollama
- Pre-commit hooks are configured to scan for secrets

---

## License

MIT
