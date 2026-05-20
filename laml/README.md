# LAML — Local Agent Memory Layer

LAML is the product folder inside [local-agent-memory-layer](../README.md). It provides:

1. **Persistent agent memory** — working memory, long-term semantic recall, auto-classification, checkpoints.
2. **Built-in token efficiency** — [Headroom](https://github.com/chopratejas/headroom) + [RTK](https://github.com/rtk-ai/rtk) embedded so memory and shell/MCP traffic use far fewer tokens.

## Layout

| Path | Purpose |
|------|---------|
| [`laml-server/`](laml-server/) | Python MCP server, HTTP API, CLI (`laml`), token-efficiency module |
| [`laml-server/docs/TOKEN_EFFICIENCY.md`](laml-server/docs/TOKEN_EFFICIENCY.md) | RTK + Headroom architecture and configuration |
| [`dashboard/`](dashboard/) | Optional monitoring UI (Vite + React) |
| [`scripts/`](scripts/) | LaunchAgents, `setup-token-optimization.sh` |

## Quick start

```bash
cd laml-server
./scripts/bootstrap.sh
# Restart Cursor; enable laml + headroom MCP servers
source .venv/bin/activate
laml token-tools status
```

## Why LAML vs memory-only MCP servers?

- **Remembers** decisions, workflows, and preferences across sessions.
- **Compresses** its own MCP JSON before the model sees it (no extra agent prompting).
- **Optimizes** shell output via RTK for all projects once hooks are installed.
- **One CLI** (`laml token-tools setup | status | update`) for memory + token tooling.

See the full server README: [laml-server/README.md](laml-server/README.md).
