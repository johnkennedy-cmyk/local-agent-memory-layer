# Firebolt Memory Layer (FML) Server

An MCP server that provides intelligent memory management for LLM applications, using Firebolt as the data layer.

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
- Firebolt account with database and engine
- OpenAI API key (for embeddings)
- Ollama installed locally (for classification)

### Setup

1. **Clone and install dependencies:**
   ```bash
   cd fml-server
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

4. **Test connections:**
   ```bash
   python scripts/test_connections.py
   ```

5. **Run database migrations:**
   ```bash
   python scripts/migrate.py
   ```

6. **Start the MCP server:**
   ```bash
   python -m src.server
   ```

## Using with MCP Clients

FML works with any MCP-compatible client. See **[Platform Setup Guide](docs/MCP_PLATFORM_SETUP.md)** for detailed instructions for:
- **Claude Code** (Anthropic)
- **Google Gemini** / Antigravity Codes
- **Cursor IDE** (current setup)

### Quick Setup for Cursor

Add to your Cursor settings (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "fml": {
      "command": "/path/to/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/fml-server",
      "env": {
        "PYTHONPATH": "/path/to/fml-server"
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
| `OPENAI_API_KEY` | OpenAI API key for embeddings |
| `FIREBOLT_ACCOUNT_NAME` | Firebolt account name |
| `FIREBOLT_CLIENT_ID` | Firebolt client ID |
| `FIREBOLT_CLIENT_SECRET` | Firebolt client secret |
| `FIREBOLT_DATABASE` | Firebolt database name |
| `FIREBOLT_ENGINE` | Firebolt engine name |
| `OLLAMA_HOST` | Ollama server URL (default: http://localhost:11434) |
| `OLLAMA_MODEL` | Ollama model to use (default: mistral:7b) |

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
│  FML MCP Server                                         │
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
