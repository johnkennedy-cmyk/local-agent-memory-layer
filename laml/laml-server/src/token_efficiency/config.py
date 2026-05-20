"""Configuration for LAML token efficiency (Headroom + RTK)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() not in ("0", "false", "no", "off")


@dataclass(frozen=True)
class TokenEfficiencyConfig:
    """Runtime settings for embedded token optimization."""

    headroom_compress_mcp: bool = True
    headroom_min_tokens: int = 400
    setup_rtk_on_bootstrap: bool = True
    setup_headroom_mcp_on_bootstrap: bool = True
    setup_rtk_cursor_hook: bool = True
    headroom_proxy_port: int = 8787
    weekly_update_enabled: bool = True

    @classmethod
    def from_env(cls) -> TokenEfficiencyConfig:
        return cls(
            headroom_compress_mcp=_env_bool("LAML_HEADROOM_COMPRESS", True),
            headroom_min_tokens=int(os.getenv("LAML_HEADROOM_MIN_TOKENS", "400")),
            setup_rtk_on_bootstrap=_env_bool("LAML_SETUP_RTK", True),
            setup_headroom_mcp_on_bootstrap=_env_bool("LAML_SETUP_HEADROOM_MCP", True),
            setup_rtk_cursor_hook=_env_bool("LAML_SETUP_RTK_CURSOR_HOOK", True),
            headroom_proxy_port=int(os.getenv("LAML_HEADROOM_PROXY_PORT", "8787")),
            weekly_update_enabled=_env_bool("LAML_TOKEN_TOOLS_WEEKLY_UPDATE", True),
        )


def load_config() -> TokenEfficiencyConfig:
    return TokenEfficiencyConfig.from_env()


def laml_server_root() -> Path:
    return Path(__file__).resolve().parents[2]


