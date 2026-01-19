# FML Server - Setup Complete! ✅

## What's Been Done

1. ✅ **Repository Cloned** - Successfully cloned from `firebolt-analytics/fml`
2. ✅ **Python Environment** - Created virtual environment with Python 3.14
3. ✅ **Dependencies Installed** - All required packages installed including:
   - firebolt-sdk
   - openai
   - ollama
   - mcp (Model Context Protocol)
   - pydantic
   - pytest (dev dependencies)
4. ✅ **Configuration File** - Created `.env` file from template
5. ✅ **Build Configuration Fixed** - Updated `pyproject.toml` for proper package discovery

## Next Steps

### 1. Configure Environment Variables

Edit the `.env` file in `fml-server/` directory:

```bash
cd /Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server
nano .env  # or use your preferred editor
```

**Required Configuration:**

Based on your memory, you have Firebolt credentials. Update these values:

```env
# OpenAI API (for embeddings)
OPENAI_API_KEY=your-openai-api-key-here

# Firebolt Database Connection
FIREBOLT_ACCOUNT_NAME=se-demo-account  # From your memory
FIREBOLT_CLIENT_ID=FqIp0sNNd7GDMUAycd659LoL7KYeLgys  # From your memory
FIREBOLT_CLIENT_SECRET=your-client-secret-here
FIREBOLT_DATABASE=experimental_john  # From your memory
FIREBOLT_ENGINE=your-engine-name-here

# Ollama (for local LLM classification)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral:7b
```

### 2. Install and Start Ollama (Optional but Recommended)

```bash
brew install ollama
ollama serve  # Run in a separate terminal
ollama pull mistral:7b
```

### 3. Test Connections

```bash
cd /Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server
source .venv/bin/activate
python scripts/test_connections.py
```

### 4. Run Database Migrations

```bash
python scripts/migrate.py
```

This will create the following tables in Firebolt:
- `session_contexts` - Working memory sessions
- `working_memory_items` - Active context items
- `long_term_memories` - Persistent memories with vector embeddings
- `memory_access_log` - Access analytics

### 5. Start the MCP Server

```bash
python -m src.server
```

### 6. Configure Cursor to Use FML

Add to your Cursor MCP configuration (`.cursor/mcp.json` or Cursor settings):

```json
{
  "mcpServers": {
    "fml": {
      "command": "/Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server",
      "env": {
        "PYTHONPATH": "/Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server"
      }
    }
  }
}
```

## Project Structure

```
fml-server/
├── src/
│   ├── config.py          # Configuration management
│   ├── server.py          # MCP server entry point
│   ├── db/
│   │   ├── client.py      # Firebolt database client
│   │   └── models.py      # Data models
│   ├── llm/
│   │   ├── embeddings.py  # OpenAI embeddings
│   │   ├── ollama.py      # Ollama classification
│   │   └── openai_chat.py # OpenAI chat
│   ├── memory/
│   │   └── taxonomy.py    # Memory classification
│   └── tools/
│       ├── working_memory.py    # Working memory tools
│       ├── longterm_memory.py   # Long-term memory tools
│       └── context.py           # Context assembly
├── scripts/
│   ├── migrate.py         # Database migrations
│   ├── schema.sql         # Database schema
│   ├── test_connections.py # Connection tests
│   └── test_tools.py      # Tool tests
└── .env                   # Environment configuration
```

## Available MCP Tools

### Working Memory (5 tools)
- `init_session` - Initialize or resume a memory session
- `add_to_working_memory` - Add item to working memory
- `get_working_memory` - Retrieve current working memory
- `update_working_memory_item` - Update item properties
- `clear_working_memory` - Clear working memory

### Long-Term Memory (5 tools)
- `store_memory` - Store a memory with auto-classification
- `recall_memories` - Recall relevant memories using semantic search
- `update_memory` - Update an existing memory
- `forget_memory` - Delete a memory
- `forget_all_user_memories` - GDPR-compliant deletion

### Smart Context (2 tools)
- `get_relevant_context` - Assemble optimal context
- `checkpoint_working_memory` - Promote working memory to long-term

## Troubleshooting

- **Python Version**: Using Python 3.14 (meets requirement of 3.10+)
- **Firebolt Connection**: Verify credentials and engine is running
- **Ollama**: Optional - only needed for classification features
- **Import Errors**: Make sure virtual environment is activated: `source .venv/bin/activate`

## Documentation

- **README**: `fml-server/README.md`
- **Executive Summary**: `EXECUTIVE_SUMMARY.md`
- **Project Plan**: `PROJECT_PLAN.md`
- **Spec**: `SPEC.md`
