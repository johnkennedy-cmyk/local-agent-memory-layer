# Token efficiency (embedded in LAML)

> **Value proposition:** LAML is not only a memory MCP server — it reduces token spend on memory recalls, shell output, and other MCP tools in the same install. See also the [server README](../README.md) and [repo root README](../../../README.md).

LAML ships with **[Headroom](https://github.com/chopratejas/headroom)** and **[RTK](https://github.com/rtk-ai/rtk)** so you get:

1. **Local memory** — LAML MCP tools (sessions, recall, store, checkpoint).
2. **Token-efficient memory responses** — every LAML tool output is compressed via Headroom before it reaches the agent.
3. **Token-efficient shell commands** — RTK rewrites `git`, `test`, `docker`, etc. in Cursor/Claude (60–90% smaller).
4. **Token-efficient other MCP tools** — optional Headroom MCP server compresses non-LAML tool results.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Your agent (Cursor, Claude Code, Codex, …)                 │
├─────────────────────────────────────────────────────────────┤
│  Shell tool ──► RTK hook (hooks.json) ──► compact output    │
│  LAML MCP   ──► Headroom (in-server)  ──► compact JSON      │
│  Other MCP  ──► Headroom MCP server   ──► compress/retrieve │
│  LLM API    ──► Headroom proxy (opt.) ──► compact prompts   │
└─────────────────────────────────────────────────────────────┘
```

## Quick setup

After LAML bootstrap:

```bash
cd laml-server
source .venv/bin/activate
laml token-tools setup
```

Or from any agent via MCP: `setup_token_optimization`.

## CLI

| Command | Purpose |
|---------|---------|
| `laml token-tools setup` | Install RTK + Headroom, configure Cursor MCP + hooks, weekly updates |
| `laml token-tools status` | Versions, config flags, session compression metrics |
| `laml token-tools update` | `brew upgrade rtk` + `pip upgrade headroom-ai` in LAML venv |
| `laml setup` | Cursor `mcp.json` for LAML + token tools |

## MCP tools

| Tool | Purpose |
|------|---------|
| `get_token_optimization_status` | Check RTK/Headroom and compression stats |
| `setup_token_optimization` | Run full setup from the agent |
| `update_token_optimization_tools` | Upgrade external tools |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LAML_HEADROOM_COMPRESS` | `true` | Compress all LAML MCP tool JSON responses |
| `LAML_HEADROOM_MIN_TOKENS` | `400` | Minimum payload size before compressing |
| `LAML_SETUP_RTK` | `true` | Install RTK during `laml token-tools setup` |
| `LAML_SETUP_HEADROOM_MCP` | `true` | Add Headroom MCP entry to `~/.cursor/mcp.json` |
| `LAML_SETUP_RTK_CURSOR_HOOK` | `true` | Register RTK Cursor hook |
| `LAML_TOKEN_TOOLS_WEEKLY_UPDATE` | `true` | Install macOS weekly launchd job |

## Weekly updates

`laml token-tools setup` installs `com.laml.token-tools-weekly` (Mondays 09:00) running:

`laml token-tools update` → log: `~/Library/Logs/laml-token-tools-update.log`

## RTK vs Headroom

| Tool | Layer | What it optimizes |
|------|-------|-------------------|
| **RTK** | Shell / CLI | `git status`, tests, linters, `docker ps`, etc. |
| **Headroom (in LAML)** | LAML MCP responses | `recall_memories`, `get_working_memory`, stats JSON |
| **Headroom MCP** | Other MCP servers | Slack, DB, custom MCP tool outputs |
| **Headroom proxy** | LLM API (optional) | Full request/response path via base URL override |

RTK is a separate binary (`brew install rtk`). Headroom is a Python dependency of `laml-server`.

## Disable compression

Set in `~/.cursor/mcp.json` under the `laml` server env:

```json
"LAML_HEADROOM_COMPRESS": "false"
```

Restart Cursor after changing MCP config.
