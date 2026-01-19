# Local Setup Guide for FML Server

## Prerequisites Check

✅ **Python Version**: The project requires Python 3.10+, but you currently have Python 3.9.6
⚠️ **Action Required**: Install Python 3.10+ using Homebrew:
```bash
brew install python@3.11
# Or
brew install python@3.12
```

After installation, use the specific version:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

## Setup Steps

### 1. Create Virtual Environment

```bash
cd /Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server
python3.11 -m venv .venv  # Use Python 3.10+ version
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Configure Environment Variables

```bash
cp config/env.example .env
# Edit .env with your actual credentials
```

Required environment variables:
- `OPENAI_API_KEY` - Your OpenAI API key for embeddings
- `FIREBOLT_ACCOUNT_NAME` - Your Firebolt account name
- `FIREBOLT_CLIENT_ID` - Firebolt service account client ID
- `FIREBOLT_CLIENT_SECRET` - Firebolt service account client secret
- `FIREBOLT_DATABASE` - Firebolt database name
- `FIREBOLT_ENGINE` - Firebolt engine name
- `OLLAMA_HOST` - Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL` - Ollama model (default: mistral:7b)

### 4. Install and Start Ollama (Optional but Recommended)

```bash
brew install ollama
ollama serve  # Run in a separate terminal
ollama pull mistral:7b
```

### 5. Test Connections

```bash
python scripts/test_connections.py
```

### 6. Run Database Migrations

```bash
python scripts/migrate.py
```

### 7. Start the MCP Server

```bash
python -m src.server
```

## Using with Cursor

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

## Troubleshooting

- **Python Version**: Ensure you're using Python 3.10+
- **Firebolt Connection**: Verify your credentials and that your engine is running
- **Ollama**: Make sure Ollama is running if you're using classification features
- **Dependencies**: If installation fails, try upgrading pip first: `pip install --upgrade pip`
