# Elasticsearch as Vector Backend for LAML

You can use **Elasticsearch** instead of Firebolt for long-term memory and vector search. Sessions, working memory, and auxiliary tables (relationships, access log) still use Firebolt.

## 1. Set vector backend

In your `.env` (copy from `config/env.example`):

```bash
LAML_VECTOR_BACKEND=elastic
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=laml_long_term_memories
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

This creates the index `laml_long_term_memories` with the correct `dense_vector` mapping.

## 4. Start LAML

Run the LAML MCP server as usual (e.g. via Cursor). It will use Elasticsearch for long-term memory and vector search; Firebolt is still required for sessions and working memory.

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

- When `LAML_VECTOR_BACKEND=elastic`, dashboard **memory count** comes from Elasticsearch; **category breakdown** and **top accessed** are only available when using the Firebolt backend.
- Quality and maintenance tools that run SQL over `long_term_memories` are written for Firebolt; they are not used when the Elastic backend is selected for long-term memory.
