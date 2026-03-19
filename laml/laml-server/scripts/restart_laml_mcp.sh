#!/usr/bin/env bash
# Restart the LAML MCP server by stopping any running "python -m src.server"
# process. Cursor will start a new one (with current .env) on next LAML tool use.
#
# See: docs/START_AND_RESTART.md

set -e
cd "$(dirname "$0")/.."

echo "Checking for LAML MCP server process (python -m src.server)..."

if ! command -v pgrep >/dev/null 2>&1; then
  echo "pgrep not found; try: pkill -f 'python -m src.server'"
  exit 1
fi

PIDS=$(pgrep -f "python -m src.server" 2>/dev/null || true)
if [ -z "$PIDS" ]; then
  echo "No running LAML MCP server process found."
  echo "Cursor will start a new one when you next use a LAML tool."
  exit 0
fi

echo "Stopping LAML MCP server PID(s): $PIDS"
for pid in $PIDS; do
  kill -TERM "$pid" 2>/dev/null || true
done
sleep 1
# Confirm gone
REMAIN=$(pgrep -f "python -m src.server" 2>/dev/null || true)
if [ -n "$REMAIN" ]; then
  echo "Some process(es) still running: $REMAIN (may need kill -9)"
  exit 1
fi
echo "Done. Use a LAML tool in Cursor to start a fresh server with current .env."
