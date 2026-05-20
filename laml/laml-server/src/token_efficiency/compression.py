"""Compress LAML MCP tool outputs via Headroom before they reach the agent."""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable

from src.token_efficiency.config import load_config
from src.token_efficiency.metrics import record_compression

logger = logging.getLogger("laml-server.token-efficiency")


def _extract_user_query(tool_args: dict[str, Any] | None) -> str:
    if not tool_args:
        return ""
    for key in ("query", "content"):
        value = tool_args.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def compress_mcp_output(
    content: str,
    *,
    tool_name: str,
    tool_args: dict[str, Any] | None = None,
) -> str:
    """Compress a JSON tool response when Headroom is installed."""
    config = load_config()
    if not config.headroom_compress_mcp or not isinstance(content, str):
        return content

    try:
        from headroom.integrations.mcp import compress_tool_result_with_metrics
    except ImportError:
        logger.debug("headroom-ai not installed; skipping MCP output compression")
        return content

    try:
        result = compress_tool_result_with_metrics(
            content=content,
            tool_name=f"laml_{tool_name}",
            tool_args=tool_args or {},
            user_query=_extract_user_query(tool_args),
        )
        record_compression(
            tool_name=tool_name,
            original_tokens=result.original_tokens,
            compressed_tokens=result.compressed_tokens,
            was_compressed=result.was_compressed,
        )
        if result.was_compressed:
            logger.info(
                "Headroom compressed %s: %d -> %d tokens (%.0f%% saved)",
                tool_name,
                result.original_tokens,
                result.compressed_tokens,
                result.compression_ratio * 100,
            )
        return result.compressed_content
    except Exception as exc:
        logger.warning("Headroom compression failed for %s: %s", tool_name, exc)
        return content


def _maybe_compress_result(
    result: Any,
    *,
    tool_name: str,
    tool_args: dict[str, Any] | None,
) -> Any:
    if isinstance(result, str):
        return compress_mcp_output(result, tool_name=tool_name, tool_args=tool_args)
    return result


def wrap_tool_fn(fn: Callable[..., Any], *, tool_name: str) -> Callable[..., Any]:
    """Wrap a LAML tool so string responses pass through Headroom compression."""

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await fn(*args, **kwargs)
            return _maybe_compress_result(result, tool_name=tool_name, tool_args=kwargs)

        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        result = fn(*args, **kwargs)
        return _maybe_compress_result(result, tool_name=tool_name, tool_args=kwargs)

    return sync_wrapper


def install_tool_output_compression(mcp: Any) -> None:
    """Patch FastMCP.add_tool so every registered tool compresses outputs."""
    config = load_config()
    if not config.headroom_compress_mcp:
        logger.info("LAML_HEADROOM_COMPRESS disabled; MCP output compression off")
        return

    original_add_tool = mcp.add_tool

    def add_tool_with_compression(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        name = kwargs.get("name") or getattr(fn, "__name__", "tool")
        wrapped = wrap_tool_fn(fn, tool_name=str(name))
        return original_add_tool(wrapped, *args, **kwargs)

    mcp.add_tool = add_tool_with_compression  # type: ignore[method-assign]
    logger.info("LAML MCP tool output compression enabled (Headroom)")
