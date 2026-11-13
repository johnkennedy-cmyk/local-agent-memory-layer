#!/bin/bash
# LAML Bootstrap Script — memory layer + token efficiency (RTK + Headroom)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAML_SERVER_DIR="$(dirname "$SCRIPT_DIR")"
LAML_DIR="$(dirname "$LAML_SERVER_DIR")"
REPO_DIR="$(dirname "$LAML_DIR")"

echo "LAML Bootstrap"
echo "=============="
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1 found"
        return 0
    else
        echo -e "  ${RED}✗${NC} $1 not found"
        return 1
    fi
}

echo "Checking prerequisites..."
MISSING=0
check_command python3 || MISSING=1
check_command docker || MISSING=1
check_command curl || MISSING=1

if [ $MISSING -eq 1 ]; then
    echo -e "${RED}Install missing prerequisites and run again.${NC}"
    exit 1
fi

echo ""
echo "Checking Relate (local memory)..."
if command -v relate >/dev/null 2>&1 || [ -x "$HOME/.local/bin/relate" ]; then
    echo -e "  ${GREEN}✓${NC} relate CLI"
else
    echo -e "  ${YELLOW}!${NC} relate not on PATH. Install: curl -sSfL https://relatedb.ai/install.sh | bash"
fi
if [ -d "$HOME/.relate/memory" ]; then
    echo -e "  ${GREEN}✓${NC} store ~/.relate/memory"
else
    echo -e "  ${YELLOW}!${NC} ~/.relate/memory is missing. A writable relate query creates it; read-only open will not."
fi

echo ""
echo "Setting up Python environment..."
cd "$LAML_SERVER_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

PYTHON="${LAML_SERVER_DIR}/.venv/bin/python3.11"
if [ ! -x "$PYTHON" ]; then
    PYTHON="${LAML_SERVER_DIR}/.venv/bin/python"
fi

echo "  Installing laml-server (includes Headroom for token efficiency)..."
"$PYTHON" -m pip install -q -U pip
"$PYTHON" -m pip install -q -e ".[dev]"

echo -e "  ${GREEN}✓${NC} Python environment ready"
echo ""

echo "Environment configuration..."
if [ ! -f ".env" ]; then
    cp config/env.example .env 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Created .env from template"
else
    echo -e "  ${GREEN}✓${NC} .env exists"
fi

echo ""
echo "Database schema..."
"$PYTHON" scripts/migrate.py 2>/dev/null || echo -e "  ${YELLOW}!${NC} Migration warnings (may be OK)"
"$PYTHON" scripts/seed_core_memories.py 2>/dev/null || true

echo ""
echo "Cursor + token efficiency (RTK + Headroom)..."
"$PYTHON" -m src.cli setup --token-tools 2>/dev/null || {
    echo -e "  ${YELLOW}!${NC} Run manually: laml token-tools setup"
}

# Copy LAML cursor rules
CURSOR_RULES="$HOME/.cursor/rules"
mkdir -p "$CURSOR_RULES"
if [ -f "$REPO_DIR/cursor-rules/laml-memory.mdc" ]; then
    cp "$REPO_DIR/cursor-rules/laml-memory.mdc" "$CURSOR_RULES/"
    echo -e "  ${GREEN}✓${NC} LAML rules → ~/.cursor/rules/"
fi

echo ""
echo "=============="
echo -e "${GREEN}LAML bootstrap complete${NC}"
echo "=============="
echo ""
echo "Next steps:"
echo "  1. Local memory is the Relate store at ~/.relate/memory (see AGENTS.md)"
echo "  2. Restart Cursor (Cmd+Q, reopen)"
echo "  3. Enable the relate MCP server (http://127.0.0.1:8399/mcp) plus headroom"
echo "  4. Check token tools: laml token-tools status"
echo ""
