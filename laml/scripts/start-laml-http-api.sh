#!/bin/bash
# Start LAML HTTP API (dashboard backend). Used by LaunchAgent or manually.
# Set LAML_REPO_ROOT to repo root if not running from this directory.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${LAML_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$REPO_ROOT/laml/laml-server"
export PYTHONPATH="$REPO_ROOT/laml/laml-server"
exec .venv/bin/python -m src.http_api
