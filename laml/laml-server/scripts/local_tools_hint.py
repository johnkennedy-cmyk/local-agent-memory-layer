#!/usr/bin/env python3
"""Show where local-only internal scripts are stored."""

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    local_dir = root / "local-only" / "internal-scripts"

    print("LAML Local-Only Tools")
    print("=" * 24)
    print(f"Path: {local_dir}")
    print()
    print("This folder is intentionally git-ignored and never pushed.")
    print("Use it for one-off migrations, diagnostics, and private runbooks.")
    print()
    print("Common examples:")
    print(f"  python {local_dir}/migrate_firebolt_to_elastic.py")
    print(f"  python {local_dir}/migrate_firebolt_to_clickhouse.py")
    print(f"  python {local_dir}/session_summary.py")
    print()
    if not local_dir.exists():
        print("Note: local-only/internal-scripts/ does not exist yet on this machine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
