#!/usr/bin/env python3
"""LAML MCP Server - Main entry point."""

import logging
import os
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.tools.context import register_context_tools
from src.tools.longterm_memory import register_longterm_memory_tools
from src.tools.quality import register_quality_tools
from src.tools.stats import register_stats_tools
from src.tools.working_memory import register_working_memory_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("laml-server")


def _maybe_start_http_api_and_dashboard() -> None:
    """
    Best-effort auto-start of HTTP API and dashboard when LAML starts.

    - Starts `python -m src.http_api` in the server cwd if not already running.
    - Starts `npm run dev` in the sibling `dashboard` directory if available.
    """
    cwd = Path(__file__).resolve().parents[2]  # .../laml/laml-server
    dashboard_dir = cwd.parent / "dashboard"

    # Allow opt-out via env
    if os.getenv("LAML_AUTOSTART_DASHBOARD", "true").lower() != "true":
        logger.info("LAML_AUTOSTART_DASHBOARD is not true; skipping dashboard auto-start.")
        return

    # Start HTTP API
    try:
        logger.info("Starting LAML HTTP API (src.http_api)...")
        subprocess.Popen(
            [sys.executable, "-m", "src.http_api"],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:  # pragma: no cover - best-effort
        logger.warning(f"Failed to start HTTP API automatically: {e}")

    # Start dashboard dev server if package.json exists
    if (dashboard_dir / "package.json").exists():
        try:
            logger.info("Starting LAML dashboard (npm run dev)...")
            subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=str(dashboard_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:  # pragma: no cover - best-effort
            logger.warning(f"Failed to start dashboard automatically: {e}")
    else:
        logger.info("Dashboard directory present but no package.json; skipping dashboard auto-start.")


# Create FastMCP server instance
mcp = FastMCP(
    name="local-agent-memory-layer",
    instructions="""
LAML (Local Agent Memory Layer) provides intelligent memory management for LLMs using a local vector database.

Available tools:
- init_session: Start or resume a memory session
- add_to_working_memory: Add items to current session's working memory
- get_working_memory: Retrieve current working memory state
- update_working_memory_item: Update item properties (pinned, relevance)
- clear_working_memory: Clear session working memory
- store_memory: Store content in long-term memory with auto-classification
- recall_memories: Search long-term memory with semantic similarity
- update_memory: Update existing long-term memory
- forget_memory: Delete a memory (soft delete by default)
- get_relevant_context: Smart context assembly from all memory sources
- checkpoint_working_memory: Promote working memory to long-term storage
- get_laml_stats: Get server statistics and metrics for monitoring
- get_recent_calls: Get recent API calls for a service
- get_memory_analytics: Get detailed memory analytics and distribution
- memory_quality_report: Generate memory health report
- find_memory_contradictions: Find potentially outdated/contradictory memories
- supersede_memory: Mark old memory as replaced by newer one
- apply_memory_decay: Reduce importance of unused memories
- run_daily_maintenance: Run backup, decay, and quality checks
""",
)


def setup_server():
    """Register all tools and auto-start monitoring components."""
    logger.info("Registering MCP tools...")

    register_working_memory_tools(mcp)
    logger.info("  ✓ Working memory tools registered")

    register_longterm_memory_tools(mcp)
    logger.info("  ✓ Long-term memory tools registered")

    register_context_tools(mcp)
    logger.info("  ✓ Context tools registered")

    register_stats_tools(mcp)
    logger.info("  ✓ Stats/monitoring tools registered")

    register_quality_tools(mcp)
    logger.info("  ✓ Quality/maintenance tools registered")

    logger.info("All tools registered successfully!")

    # Auto-start HTTP API and dashboard (best-effort)
    _maybe_start_http_api_and_dashboard()


# Initialize on import
setup_server()

if __name__ == "__main__":
    # Run with stdio transport for MCP clients
    mcp.run()
