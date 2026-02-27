# ClickHouse as Vector Backend for LAML

You can use **ClickHouse** for long-term memory and vector search. Sessions and working memory still use Firebolt.

> **Important:** The ClickHouse server **must be running and healthy before** you configure the ClickHouse MCP server in Cursor. If ClickHouse is down, the MCP server will fail to start.

## 1. Set vector backend

In `.env`:

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

## 2. Run ClickHouse locally

From `laml-server/`:

```bash
docker compose -f docker-compose.clickhouse.yml up -d
```

Then wait until ClickHouse is healthy **before doing anything with the MCP server**:

```bash
curl http://localhost:8123/ping
# Should return:
# Ok.
```

If this health check fails, fix ClickHouse first (container logs, port conflicts, etc.) before moving on.

## 3. Create database and table

```bash
cd laml-server
python scripts/init_clickhouse.py
```

Run this once to create the `laml` database and `long_term_memories` table.

## 4. Configure ClickHouse MCP server in Cursor

Once **steps 2 and 3 succeed**, add the official **ClickHouse MCP server** to `~/.cursor/mcp.json` so Cursor can query ClickHouse (list tables, run SELECT).

**Option A – Docker (recommended, no uv/Python required)**

Add this entry inside the `mcpServers` block. The MCP runs in a container and connects to ClickHouse on the host via `host.docker.internal`:

```json
"clickhouse": {
  "command": "docker",
  "args": [
    "run",
    "-i",
    "--rm",
    "--add-host=host.docker.internal:host-gateway",
    "-e", "CLICKHOUSE_HOST",
    "-e", "CLICKHOUSE_PORT",
    "-e", "CLICKHOUSE_USER",
    "-e", "CLICKHOUSE_PASSWORD",
    "-e", "CLICKHOUSE_SECURE",
    "-e", "CLICKHOUSE_VERIFY",
    "mcp/clickhouse"
  ],
  "env": {
    "CLICKHOUSE_HOST": "host.docker.internal",
    "CLICKHOUSE_PORT": "8123",
    "CLICKHOUSE_USER": "default",
    "CLICKHOUSE_PASSWORD": "",
    "CLICKHOUSE_SECURE": "false",
    "CLICKHOUSE_VERIFY": "false"
  }
}
```

**Option B – uv (requires uv installed and in PATH)**

Install [uv](https://github.com/astral-sh/uv), then use the same env vars with `uv run --with mcp-clickhouse mcp-clickhouse`. Use `CLICKHOUSE_HOST=localhost` when running on the host; use `host.docker.internal` only if ClickHouse is in Docker and the MCP runs on the host.

Merge the block into your existing `mcpServers` in `~/.cursor/mcp.json`. Then **restart Cursor** (e.g. quit with Cmd+Q and reopen) so it picks up the new MCP server.

## 5. Start LAML

Run the LAML MCP server as usual. It will use ClickHouse for long-term memory and vector search.

## Tools provided by ClickHouse MCP

- `run_query` – run SQL (read-only by default)
- `list_databases` – list databases
- `list_tables` – list tables in a database

These let the AI inspect and query your ClickHouse data (including LAML tables) from Cursor.
