#!/usr/bin/env python3
"""LAML CLI — memory layer setup and token-efficiency tooling."""

from __future__ import annotations

import json
import sys

import click

from src.token_efficiency.agent_setup import (
    get_status,
    run_full_setup,
    setup_cursor_mcp,
    setup_cursor_rtk_hook,
    update_tools,
)


@click.group()
def main() -> None:
    """LAML: local agent memory + token efficiency for all LLM interactions."""


@main.group()
def token_tools() -> None:
    """RTK + Headroom: compress shell output and MCP/tool context."""


@token_tools.command("setup")
@click.option(
    "--agent",
    "agents",
    multiple=True,
    default=["cursor"],
    help="Agents to configure (cursor, claude). Default: cursor.",
)
@click.option("--no-launch-agent", is_flag=True, help="Skip weekly macOS launchd job.")
def token_tools_setup(agents: tuple[str, ...], no_launch_agent: bool) -> None:
    """Install RTK + Headroom and wire Cursor/Claude for token efficiency."""
    result = run_full_setup(agents=list(agents), install_launch_agent=not no_launch_agent)
    for line in result.get("messages", []):
        click.echo(line)
    click.echo("")
    click.echo("Restart your IDE so MCP servers and hooks reload.")


@token_tools.command("status")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def token_tools_status(as_json: bool) -> None:
    """Show RTK/Headroom install state and LAML compression metrics."""
    status = get_status()
    if as_json:
        click.echo(json.dumps(status, indent=2))
        return
    click.echo("Token efficiency status")
    click.echo("-" * 40)
    rtk = status["rtk"]
    hr = status["headroom"]
    click.echo(f"RTK:      {'✓' if rtk['installed'] else '✗'}  {rtk.get('version') or 'not installed'}")
    click.echo(f"Headroom: {'✓' if hr['installed'] else '✗'}  {hr.get('version') or 'not installed'}")
    click.echo(f"LAML MCP compression: {status['config']['headroom_compress_mcp']}")
    totals = status["compression_metrics"]["totals"]
    if totals["calls"]:
        click.echo(
            f"Session savings: {totals['tokens_saved']} tokens "
            f"({totals['savings_ratio']:.0%} across {totals['calls']} calls)"
        )


@token_tools.command("update")
def token_tools_update() -> None:
    """Upgrade RTK (brew) and Headroom (pip in LAML venv)."""
    result = update_tools()
    for line in result.get("messages", []):
        click.echo(line)


@main.command("setup")
@click.option("--token-tools/--no-token-tools", default=True, help="Configure RTK + Headroom.")
@click.option("--agent", "agents", multiple=True, default=["cursor"])
def setup(token_tools: bool, agents: tuple[str, ...]) -> None:
    """Post-bootstrap: Cursor MCP + optional token-efficiency setup."""
    click.echo("Configuring LAML in Cursor...")
    for line in setup_cursor_mcp():
        click.echo(f"  {line}")
    if token_tools:
        click.echo("")
        click.echo("Setting up token efficiency (RTK + Headroom)...")
        result = run_full_setup(agents=list(agents))
        for line in result.get("messages", []):
            click.echo(f"  {line}")


if __name__ == "__main__":
    main()
