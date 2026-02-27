#!/bin/bash
# LAML Dashboard Startup Script
# Run from repo root or set LAML_REPO_ROOT to the path to local-agent-memory-layer.

set -e
REPO_ROOT="${LAML_REPO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$REPO_ROOT/laml/dashboard"
export PATH="/opt/homebrew/bin:$PATH"
exec npm run dev -- --host
