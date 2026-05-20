"""MCP tools for LAML token-efficiency setup and monitoring."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from src.token_efficiency.agent_setup import get_status, run_full_setup, update_tools


def register_token_efficiency_tools(mcp: FastMCP) -> None:
    """Register token optimization tools with the MCP server."""

    @mcp.tool()
    async def get_token_optimization_status() -> str:
        """
        Report RTK/Headroom installation and LAML compression metrics.

        Use at session start to confirm token-efficiency tooling is active.
        """
        return json.dumps(get_status(), indent=2)

    @mcp.tool()
    async def setup_token_optimization(
        agents: str = "cursor",
        install_weekly_updates: bool = True,
    ) -> str:
        """
        Install/configure RTK + Headroom for LAML and other coding agents.

        Args:
            agents: Comma-separated agents to configure (e.g. 'cursor' or 'cursor,claude')
            install_weekly_updates: Schedule weekly RTK/Headroom upgrades (macOS launchd)
        """
        agent_list = [a.strip() for a in agents.split(",") if a.strip()]
        result = run_full_setup(
            agents=agent_list or ["cursor"],
            install_launch_agent=install_weekly_updates,
        )
        return json.dumps(
            {
                "ok": True,
                "agents": agent_list,
                "messages": result.get("messages", []),
                "note": "Restart your IDE after setup so MCP servers and hooks reload.",
            },
            indent=2,
        )

    @mcp.tool()
    async def update_token_optimization_tools() -> str:
        """Upgrade RTK and Headroom to latest versions."""
        result = update_tools()
        return json.dumps({"ok": True, "messages": result.get("messages", [])}, indent=2)
