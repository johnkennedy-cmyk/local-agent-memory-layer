#!/usr/bin/env bash
# Configure RTK + Headroom for LAML and all supported coding agents.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAML_SERVER_DIR="$(dirname "$SCRIPT_DIR")/laml-server"
PYTHON="${LAML_SERVER_DIR}/.venv/bin/python3.11"

if [[ ! -x "${PYTHON}" ]]; then
  echo "LAML venv not found. Run laml-server/scripts/bootstrap.sh first."
  exit 1
fi

cd "${LAML_SERVER_DIR}"
exec "${PYTHON}" -m pip install -q -e . && "${PYTHON}" -m src.cli token-tools setup "$@"
