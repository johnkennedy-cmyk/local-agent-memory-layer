# Elasticsearch as Vector Backend for LAML

You can use **Elasticsearch** as the **single backend** for LAML: long-term memory, sessions, and working memory all use Elasticsearch. Firebolt is **not required** when `LAML_VECTOR_BACKEND=elastic`.

## 1. Set vector backend

In your `.env` (copy from `config/env.example`):

```bash
LAML_VECTOR_BACKEND=elastic
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=laml_long_term_memories
# Optional: override default index names for sessions and working memory
# ELASTICSEARCH_SESSIONS_INDEX=laml_sessions
# ELASTICSEARCH_WORKING_MEMORY_INDEX=laml_working_memory
# Optional auth (leave empty for local single-node with security disabled):
# ELASTICSEARCH_API_KEY=
# ELASTICSEARCH_USERNAME=
# ELASTICSEARCH_PASSWORD=
ELASTICSEARCH_SSL_VERIFY=true
ELASTICSEARCH_EMBEDDING_DIMENSIONS=768
```

## 2. Run Elasticsearch locally

From `laml-server`:

```bash
docker compose -f docker-compose.elastic.yml up -d
```

Wait until Elasticsearch is healthy (`curl http://localhost:9200/_cluster/health` returns green or yellow).

## 3. Create the LAML index

With the same `.env` and virtualenv activated:

```bash
cd /path/to/laml/laml-server
python scripts/init_elastic_index.py
```

This creates the indices `laml_long_term_memories`, `laml_sessions`, and `laml_working_memory` with the correct mappings.

## 4. Start LAML

Run the LAML MCP server as usual (e.g. via Cursor). It will use Elasticsearch for **all** persistence: long-term memory, sessions, and working memory. Firebolt is not required.

## Optional: Elastic MCP server for Cursor

To let Cursor (or other MCP clients) query Elasticsearch directly (list indices, run searches, ES|QL), you can run the official Elastic MCP server.

**Option A – Docker (stdio, recommended for Cursor)**

Add to `~/.cursor/mcp.json` (adjust paths and ensure Elasticsearch is reachable):

```json
{
  "mcpServers": {
    "laml": { "..." },
    "elasticsearch": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e", "ES_URL=http://host.docker.internal:9200",
        "docker.elastic.co/mcp/elasticsearch",
        "stdio"
      ]
    }
  }
}
```

If Elasticsearch has security enabled, add `-e ES_API_KEY=your-api-key` (and pass the key via env or a secure mechanism).

**Option B – Docker Compose profile**

```bash
docker compose -f docker-compose.elastic.yml --profile mcp up -d
```

The MCP server in the compose file is intended for HTTP mode; for Cursor stdio use Option A.

## Notes

- When `LAML_VECTOR_BACKEND=elastic`, the dashboard **memory count**, **sessions**, and **working memory** stats all come from Elasticsearch. **Category breakdown**, **top accessed**, and **storage (SHOW TABLES)** are only available when using the Firebolt backend.
- Quality and maintenance tools that run SQL over `long_term_memories` are written for Firebolt; they are not used when the Elastic backend is selected.

### Migration notes

For new users, the recommended path is to start clean on the selected backend.
If you need one-time legacy data migration from Firebolt, keep migration helpers in your local-only workspace and do not include them in upstream commits.
