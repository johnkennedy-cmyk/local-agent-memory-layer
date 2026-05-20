"""Aggregate Headroom compression metrics for LAML MCP tools."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class CompressionTotals:
    calls: int = 0
    compressed_calls: int = 0
    original_tokens: int = 0
    compressed_tokens: int = 0
    tokens_saved: int = 0

    @property
    def savings_ratio(self) -> float:
        if self.original_tokens <= 0:
            return 0.0
        return self.tokens_saved / self.original_tokens

    def to_dict(self) -> dict:
        return {
            "calls": self.calls,
            "compressed_calls": self.compressed_calls,
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "tokens_saved": self.tokens_saved,
            "savings_ratio": round(self.savings_ratio, 4),
        }


_lock = threading.Lock()
_totals = CompressionTotals()
_by_tool: dict[str, CompressionTotals] = {}


def record_compression(
    *,
    tool_name: str,
    original_tokens: int,
    compressed_tokens: int,
    was_compressed: bool,
) -> None:
    global _totals, _by_tool
    saved = max(0, original_tokens - compressed_tokens)
    with _lock:
        _totals.calls += 1
        _totals.original_tokens += original_tokens
        _totals.compressed_tokens += compressed_tokens
        _totals.tokens_saved += saved
        if was_compressed:
            _totals.compressed_calls += 1

        bucket = _by_tool.setdefault(tool_name, CompressionTotals())
        bucket.calls += 1
        bucket.original_tokens += original_tokens
        bucket.compressed_tokens += compressed_tokens
        bucket.tokens_saved += saved
        if was_compressed:
            bucket.compressed_calls += 1


def get_metrics() -> dict:
    with _lock:
        return {
            "totals": _totals.to_dict(),
            "by_tool": {name: totals.to_dict() for name, totals in _by_tool.items()},
        }
