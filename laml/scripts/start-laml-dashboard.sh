#!/bin/bash
# Start LAML Dashboard (Vite). Used by LaunchAgent or manually.
# Set LAML_REPO_ROOT to repo root if not running from this directory.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${LAML_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$REPO_ROOT/laml/dashboard"
export PATH="/opt/homebrew/bin:$PATH"
exec npm run dev -- --host
