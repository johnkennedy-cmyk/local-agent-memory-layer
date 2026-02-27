#!/usr/bin/env python3
"""Backend + MCP health checks for LAML."""

import json
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config  # noqa: E402


def print_header():
    print("=" * 60)
    print("LAML - Backend & MCP Health Checks")
    print("=" * 60)


def check_firebolt_core():
    """Check Firebolt Core (local) when configured."""
    if not config.firebolt.use_core:
        print("\nFirebolt Core backend not enabled (FIREBOLT_USE_CORE!=true). Skipping.")
        return True

    print("\n1. Checking Firebolt Core backend...")
    print(f"   URL: {config.firebolt.core_url}")
    print(f"   Database: {config.firebolt.database or '(not set)'}")

    try:
        from src.db.client import db

        result = db.execute("SELECT 1 AS test")
        print(f"   ✓ Firebolt Core reachable. Result: {result}")
        return True
    except Exception as e:
        print(f"   ✗ Firebolt Core check failed: {e}")
        print("   Hint: Ensure Firebolt Core is running and FIREBOLT_DATABASE is configured.")
        return False


def check_cursor_mcp_config():
    """Check that a matching MCP server entry exists in Cursor config."""
    print("\n2. Checking Cursor MCP configuration...")
    mcp_path = Path.home() / ".cursor" / "mcp.json"
    if not mcp_path.exists():
        print(f"   ✗ No Cursor MCP config found at {mcp_path}")
        print("   Hint: Add a 'laml' entry pointing at this server.")
        return False

    try:
        data = json.loads(mcp_path.read_text())
    except Exception as e:
        print(f"   ✗ Failed to parse {mcp_path}: {e}")
        return False

    servers = data.get("mcpServers") or data.get("mcp_servers") or {}
    has_laml = "laml" in servers
    has_firebolt = "firebolt" in servers

    if has_laml:
        print("   ✓ 'laml' MCP server entry found in Cursor config.")
    else:
        print("   ✗ 'laml' MCP server entry NOT found in Cursor config.")
        print("   Hint: Add a 'laml' entry for the Local Agent Memory Layer.")

    if config.firebolt.use_core:
        if has_firebolt:
            print("   ✓ 'firebolt' MCP server entry found (optional, for SQL queries).")
        else:
            print("   ⚠️  'firebolt' MCP server entry NOT found.")
            print("      Hint: For best experience, also install and configure the Firebolt MCP.")

    return has_laml


def main():
    print_header()
    ok_backend = check_firebolt_core()
    ok_mcp = check_cursor_mcp_config()

    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)

    overall = ok_backend and ok_mcp

    print(f"  Backend OK: {'✓' if ok_backend else '✗'}")
    print(f"  MCP Config OK: {'✓' if ok_mcp else '✗'}")
    print("=" * 60)

    if overall:
        print("\n🎉 Backend and MCP configuration look good.")
    else:
        print("\n⚠️  Please address the issues above for the best LAML experience.")

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
