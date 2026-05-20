#!/usr/bin/env python3
"""Stdio entrypoint for Headroom MCP (avoids loading full headroom CLI / proxy deps)."""

from __future__ import annotations

import asyncio
import logging
import os


async def _run() -> None:
    from headroom.ccr.mcp_server import create_ccr_mcp_server

    proxy_url = os.getenv("HEADROOM_PROXY_URL", "http://127.0.0.1:8787")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    server = create_ccr_mcp_server(proxy_url=proxy_url)
    try:
        await server.run_stdio()
    finally:
        await server.cleanup()


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
