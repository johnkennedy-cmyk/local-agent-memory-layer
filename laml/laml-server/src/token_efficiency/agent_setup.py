"""Install and configure RTK + Headroom for LAML and other coding agents."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.token_efficiency.config import TokenEfficiencyConfig, laml_server_root, load_config


def headroom_python() -> Path:
    root = laml_server_root()
    for name in ("python3.11", "python3", "python"):
        candidate = root / ".venv" / "bin" / name
        if candidate.is_file():
            return candidate
    return Path("python3")


def headroom_installed() -> tuple[bool, str | None]:
    try:
        from headroom._version import __version__

        return True, __version__
    except ImportError:
        return False, None


def _run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _which(name: str) -> str | None:
    return shutil.which(name)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _merge_mcp_server(
    config: dict[str, Any],
    name: str,
    entry: dict[str, Any],
) -> bool:
    servers = config.setdefault("mcpServers", {})
    existing = servers.get(name)
    if existing == entry:
        return False
    servers[name] = entry
    return True


def build_laml_mcp_entry(server_dir: Path | None = None) -> dict[str, Any]:
    root = server_dir or laml_server_root()
    python = root / ".venv" / "bin" / "python3.11"
    if not python.is_file():
        python = root / ".venv" / "bin" / "python"
    return {
        "command": str(python) if python.is_file() else "python3",
        "args": ["-m", "src.server"],
        "cwd": str(root),
        "env": {
            "PYTHONPATH": str(root),
            "LAML_HEADROOM_COMPRESS": "true",
        },
    }


def build_headroom_mcp_entry() -> dict[str, Any]:
    root = laml_server_root()
    return {
        "command": str(headroom_python()),
        "args": ["-m", "src.token_efficiency.headroom_mcp_entry"],
        "cwd": str(root),
        "env": {"PYTHONPATH": str(root)},
    }


def setup_cursor_mcp(config: TokenEfficiencyConfig | None = None) -> list[str]:
    """Merge LAML + Headroom into ~/.cursor/mcp.json."""
    cfg = config or load_config()
    messages: list[str] = []
    mcp_path = Path.home() / ".cursor" / "mcp.json"
    data = _read_json(mcp_path)
    if "mcpServers" not in data and mcp_path.is_file():
        messages.append(f"Could not parse {mcp_path}; skipped MCP merge")
        return messages

    changed = False
    if _merge_mcp_server(data, "laml", build_laml_mcp_entry()):
        changed = True
        messages.append("Updated laml MCP server in ~/.cursor/mcp.json")

    if cfg.setup_headroom_mcp_on_bootstrap:
        if _merge_mcp_server(data, "headroom", build_headroom_mcp_entry()):
            changed = True
            messages.append("Updated headroom MCP server in ~/.cursor/mcp.json")

    if changed:
        _write_json(mcp_path, data)
    else:
        messages.append("Cursor mcp.json already up to date")
    return messages


def setup_cursor_rtk_hook(config: TokenEfficiencyConfig | None = None) -> list[str]:
    """Ensure RTK preToolUse hook exists in ~/.cursor/hooks.json."""
    cfg = config or load_config()
    if not cfg.setup_rtk_cursor_hook:
        return ["RTK Cursor hook setup skipped (LAML_SETUP_RTK_CURSOR_HOOK=false)"]

    if not _which("rtk"):
        return ["RTK not installed; run: brew install rtk"]

    result = _run(["rtk", "init", "-g", "--agent", "cursor", "--auto-patch"], check=False)
    if result.returncode == 0:
        return ["RTK Cursor hook registered via rtk init"]
    # Fallback: merge hooks.json manually
    hooks_path = Path.home() / ".cursor" / "hooks.json"
    data = _read_json(hooks_path)
    hooks = data.setdefault("hooks", {})
    pre = hooks.setdefault("preToolUse", [])
    entry = {"command": "rtk hook cursor", "matcher": "Shell"}
    if entry not in pre:
        pre.append(entry)
        data["version"] = data.get("version", 1)
        _write_json(hooks_path, data)
        return ["RTK Cursor hook added to ~/.cursor/hooks.json"]
    return [f"RTK init note: {result.stderr.strip() or 'hook may already exist'}"]


def install_rtk() -> list[str]:
    """Install RTK via Homebrew or upstream install script."""
    if _which("rtk"):
        version = _run(["rtk", "--version"]).stdout.strip()
        return [f"RTK already installed: {version}"]

    if _which("brew"):
        result = _run(["brew", "install", "rtk"], check=False)
        if result.returncode == 0:
            return ["Installed RTK via Homebrew"]
        return [f"brew install rtk failed: {result.stderr.strip()}"]

    install_sh = "https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh"
    result = _run(["bash", "-c", f"curl -fsSL {install_sh} | sh"], check=False)
    if result.returncode == 0:
        return ["Installed RTK via install.sh (~/.local/bin)"]
    return [f"RTK install failed: {result.stderr.strip()}"]


def install_headroom_in_venv() -> list[str]:
    """Ensure headroom-ai is installed in the LAML venv."""
    root = laml_server_root()
    python = root / ".venv" / "bin" / "python3.11"
    if not python.is_file():
        return ["LAML venv not found; run bootstrap first"]
    result = _run(
        [str(python), "-m", "pip", "install", "headroom-ai[mcp]>=0.22.0"],
        check=False,
    )
    if result.returncode != 0:
        return [f"headroom pip install failed: {result.stderr.strip()}"]
    return ["Installed/upgraded headroom-ai[mcp] in LAML venv"]


def setup_claude_headroom_mcp() -> list[str]:
    """Register Headroom MCP with Claude Code when CLI is available."""
    if not headroom_installed()[0]:
        return ["Headroom not installed in LAML venv"]
    headroom_cli = _which("headroom")
    if not headroom_cli:
        return [
            "Headroom MCP for Claude: merge config/claude-code-mcp.json.template into ~/.claude/mcp.json"
        ]
    result = _run([headroom_cli, "mcp", "install"], check=False)
    if result.returncode == 0:
        return ["Headroom MCP registered for detected agents (Claude Code, etc.)"]
    return [result.stdout.strip() or result.stderr.strip() or "headroom mcp install finished"]


def setup_rtk_global(agent: str = "cursor") -> list[str]:
    """Run rtk init for a given agent."""
    if not _which("rtk"):
        return ["RTK not installed"]
    cmd = ["rtk", "init", "-g", "--agent", agent, "--auto-patch"]
    result = _run(cmd, check=False)
    if result.returncode == 0:
        return [f"RTK configured for {agent}"]
    return [result.stderr.strip() or result.stdout.strip() or "rtk init completed"]


def install_weekly_launch_agent() -> list[str]:
    """Install macOS launchd job for weekly token-tool updates."""
    script = Path.home() / ".local" / "bin" / "laml-update-token-tools.sh"
    plist = Path.home() / "Library" / "LaunchAgents" / "com.laml.token-tools-weekly.plist"
    root = laml_server_root().parent.parent  # .../laml
    script_content = f"""#!/usr/bin/env bash
set -euo pipefail
cd "{laml_server_root()}"
export PATH="$HOME/Library/Python/3.11/bin:$HOME/.local/bin:/opt/homebrew/bin:$PATH"
exec "$(dirname "$0")"/../laml-server/.venv/bin/python3.11 -m src.cli token-tools update
"""
    # Prefer invoking laml CLI from venv
    python = laml_server_root() / ".venv" / "bin" / "python3.11"
    script_content = f"""#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
exec "{python}" -m src.cli token-tools update >> "$HOME/Library/Logs/laml-token-tools-update.log" 2>&1
"""
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(script_content)
    script.chmod(0o755)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.laml.token-tools-weekly</string>
  <key>ProgramArguments</key>
  <array><string>{script}</string></array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>1</integer>
    <key>Hour</key><integer>9</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
"""
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(plist_content)

    uid = os.getuid()
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist)], check=False)
    _run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], check=False)
    return [f"Weekly update scheduled: {plist}"]


def get_status() -> dict[str, Any]:
    """Return installation and configuration status."""
    cfg = load_config()
    rtk_path = _which("rtk")
    headroom_ok, headroom_version = headroom_installed()
    rtk_version = None
    if rtk_path:
        rtk_version = _run([rtk_path, "--version"]).stdout.strip()

    from src.token_efficiency.metrics import get_metrics

    return {
        "config": {
            "headroom_compress_mcp": cfg.headroom_compress_mcp,
            "setup_rtk_on_bootstrap": cfg.setup_rtk_on_bootstrap,
            "setup_headroom_mcp_on_bootstrap": cfg.setup_headroom_mcp_on_bootstrap,
            "setup_rtk_cursor_hook": cfg.setup_rtk_cursor_hook,
        },
        "rtk": {"installed": bool(rtk_path), "path": rtk_path, "version": rtk_version},
        "headroom": {
            "installed": headroom_ok,
            "embedded_in_laml": headroom_ok,
            "version": headroom_version,
            "mcp_entry": "src.token_efficiency.headroom_mcp_entry",
        },
        "cursor_mcp": (Path.home() / ".cursor" / "mcp.json").is_file(),
        "cursor_hooks": (Path.home() / ".cursor" / "hooks.json").is_file(),
        "compression_metrics": get_metrics(),
    }


def run_full_setup(
    *,
    agents: list[str] | None = None,
    install_launch_agent: bool = True,
) -> dict[str, list[str]]:
    """Run complete token-efficiency setup for LAML and other agents."""
    cfg = load_config()
    agents = agents or ["cursor"]
    results: dict[str, list[str]] = {"messages": []}

    results["messages"].extend(install_headroom_in_venv())
    if cfg.setup_rtk_on_bootstrap:
        results["messages"].extend(install_rtk())

    if "cursor" in agents:
        results["messages"].extend(setup_cursor_mcp(cfg))
        results["messages"].extend(setup_cursor_rtk_hook(cfg))
        if cfg.setup_rtk_on_bootstrap:
            results["messages"].extend(setup_rtk_global("cursor"))

    if cfg.setup_headroom_mcp_on_bootstrap:
        results["messages"].extend(setup_claude_headroom_mcp())

    if install_launch_agent and cfg.weekly_update_enabled:
        results["messages"].extend(install_weekly_launch_agent())

    return results


def update_tools() -> dict[str, list[str]]:
    """Upgrade RTK and Headroom."""
    messages: list[str] = []
    if _which("brew") and _which("rtk"):
        result = _run(["brew", "upgrade", "rtk"], check=False)
        messages.append(result.stdout.strip() or "RTK upgraded via brew")
    elif _which("rtk"):
        messages.append("RTK present (non-brew install; upgrade manually)")
    else:
        messages.extend(install_rtk())

    messages.extend(install_headroom_in_venv())
    ok, ver = headroom_installed()
    if ok and ver:
        messages.append(f"Headroom (embedded): {ver}")
    return {"messages": messages}
