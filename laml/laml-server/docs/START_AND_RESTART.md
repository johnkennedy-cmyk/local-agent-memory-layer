# LAML: Start and Restart (runbook)

This doc uses **only** the code and config in this repo as the reference for creating and starting everything.

## 1. What “everything” is

| Component | How it runs | Repo reference |
|-----------|-------------|----------------|
| **Vector backend** | Firebolt Core / Elasticsearch / ClickHouse / DuckDB – Docker or host | `docker-compose.yml`, `docker-compose.elastic.yml`, `docker-compose.clickhouse.yml`; `.env` → `LAML_VECTOR_BACKEND` |
| **LAML MCP server** | Spawned by Cursor via stdio when you use a LAML tool | `src/server.py`; Cursor config from `config/cursor-mcp.json.template` |
| **HTTP API** | Optional; for dashboard. Can auto-start when MCP starts, or via Docker | `src/http_api.py` (port **8082**); `server.py` → `_maybe_start_http_api_and_dashboard()`; `docker-compose.yml` → `laml-api` |
| **Dashboard** | Optional; React UI. Can auto-start when MCP starts, or via Docker | `../dashboard/`; `docker-compose.yml` → `laml-dashboard` (port **5174**) |

From **docker-compose.yml** (in this repo):

- The **MCP server runs outside Docker**; Cursor starts it with `command` / `args` / `cwd` / `env` from `~/.cursor/mcp.json`.
- Docker Compose runs only the **HTTP API** and **dashboard** (for monitoring).

---

## 2. One-time setup (from repo root)

Paths below are relative to **`laml/laml-server/`** unless stated.

```bash
cd laml/laml-server
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp config/env.example .env  # or create .env from README
# Edit .env: LAML_VECTOR_BACKEND (firebolt | elastic | clickhouse | duckdb), backend-specific vars
```

**Backend-specific:**

- **Firebolt**: Firebolt Core on `localhost:3473`; run `python scripts/migrate.py`.
- **Elasticsearch**: See `docs/ELASTIC_VECTOR_BACKEND.md`; run `python scripts/init_elastic_index.py` when ES is up.
- **ClickHouse**: See `docs/CLICKHOUSE_VECTOR_BACKEND.md`; run `python scripts/init_clickhouse.py` when ClickHouse is up.
- **DuckDB**: No extra service; table created on first use.

**Cursor MCP config:**

- Copy `config/cursor-mcp.json.template` into `~/.cursor/mcp.json` (merge into existing `mcpServers` if needed).
- Replace `/FULL/PATH/TO/local-agent-memory-layer/laml/laml-server` with your actual path to **this** directory (the one containing `src/server.py`).

---

## 3. Start the backend (if using Docker)

From **`laml/laml-server/`**:

- **Firebolt Core** (if you run it via Docker): start that stack first so `localhost:3473` is up.
- **Elasticsearch**:
  `docker compose -f docker-compose.elastic.yml up -d`
  Then when healthy: `python scripts/init_elastic_index.py`
- **ClickHouse**:
  `docker compose -f docker-compose.clickhouse.yml up -d`
  Then when healthy: `python scripts/init_clickhouse.py`

---

## 4. Validate before using LAML

From **`laml/laml-server/`** with venv activated:

```bash
PYTHONPATH=. python scripts/test_backends.py
```

This checks (see `scripts/test_backends.py`):

- Active vector backend from `.env` and that it’s reachable.
- Cursor MCP config has a `laml` entry.
- A quick `init_session`-style create/get against the session store.

Fix any failures before relying on LAML tools.

---

## 5. How the MCP server is started (Cursor)

Cursor starts the LAML server using **`~/.cursor/mcp.json`**:

- **command**: path to `laml-server/.venv/bin/python`
- **args**: `["-m", "src.server"]`
- **cwd**: path to `laml-server`
- **env**: `PYTHONPATH` = path to `laml-server`

So the process is: **`python -m src.server`** in **`laml-server`** with that **PYTHONPATH**. It loads **`.env`** from `cwd` and registers tools; optionally it auto-starts the HTTP API and dashboard (see `src/server.py` → `_maybe_start_http_api_and_dashboard()`).

You do **not** normally run `python -m src.server` yourself for Cursor; Cursor runs it when a LAML tool is used.

---

## 6. Restarting the LAML MCP server

The repo cannot restart Cursor itself; it can only affect the **process** Cursor started.

### Option A: Restart from Cursor (recommended)

- **Cursor Settings** → **MCP** (or **Features** → **MCP**).
- Find the **laml** server and use **Restart** (or disable then enable).

After that, Cursor spawns a new `python -m src.server` with current `.env` (e.g. `LAML_VECTOR_BACKEND=firebolt`).

### Option B: Kill the server process so Cursor starts a new one

If you can’t use the UI, you can stop the running MCP process. The next time you use a LAML tool, Cursor will start a new process (with updated `.env`).

From **`laml/laml-server/`**:

```bash
# Script provided in repo (kills processes running "python -m src.server"):
./scripts/restart_laml_mcp.sh
```

Or manually:

```bash
pkill -f "python -m src.server"
# or: kill -TERM <pid> for each pid from: pgrep -fl "src.server"
```

**Warning:** Only kill the LAML server. If you run other projects that use `src.server`, prefer Option A.

---

## 7. Start HTTP API and dashboard (optional)

- **With Docker** (from `laml/laml-server/`):
  `docker compose up -d`
  → API: http://localhost:8082, Dashboard: http://localhost:5174

- **Without Docker**: When you use a LAML tool in Cursor, `src/server.py` can auto-start the HTTP API (port **8082**) and the dashboard (port **5174**) unless you set `LAML_AUTOSTART_DASHBOARD=false`. Or run manually:
  - Terminal 1: `python -m src.http_api`  (API, port 8082)
  - Terminal 2: `cd ../dashboard && npm run dev`  (dashboard, port 5174)

---

## 8. Quick reference

| Goal | Command / action |
|------|-------------------|
| Validate backend + MCP config | `PYTHONPATH=. python scripts/test_backends.py` |
| Restart MCP server (Cursor UI) | Cursor Settings → MCP → Restart **laml** |
| Restart MCP server (kill process) | `./scripts/restart_laml_mcp.sh` then use any LAML tool |
| Start API + dashboard (Docker) | `docker compose up -d` |
| Run MCP server in terminal (stdio) | `python -m src.server` (blocks; for testing) |

All paths and behaviour above are derived from this repo: `src/server.py`, `src/http_api.py`, `docker-compose*.yml`, `config/cursor-mcp.json.template`, and `scripts/test_backends.py`.
