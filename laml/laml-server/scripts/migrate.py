#!/usr/bin/env python3
"""Database migration script for LAML server."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import db


def run_migrations():
    """Run database migrations."""
    print("=" * 60)
    print("LAML Server - Database Migration")
    print("=" * 60)

    schema_path = Path(__file__).parent / "schema.sql"

    if not schema_path.exists():
        print(f"ERROR: Schema file not found: {schema_path}")
        sys.exit(1)

    print(f"\nReading schema from: {schema_path}")

    with open(schema_path, "r") as f:
        schema_sql = f.read()

    # Split by semicolons, filter empty statements
    statements = [s.strip() for s in schema_sql.split(';') if s.strip()]

    # Filter out comment-only statements
    statements = [s for s in statements if not all(
        line.strip().startswith('--') or not line.strip()
        for line in s.split('\n')
    )]

    print(f"Found {len(statements)} SQL statements to execute\n")

    success_count = 0
    error_count = 0

    for i, stmt in enumerate(statements, 1):
        # Get first line for display
        first_line = stmt.split('\n')[0][:60]
        print(f"[{i}/{len(statements)}] {first_line}...")

        try:
            db.execute(stmt)
            print(f"         ✓ Success")
            success_count += 1
        except Exception as e:
            error_str = str(e)
            # Ignore "already exists" errors
            if "already exists" in error_str.lower():
                print(f"         ⊘ Already exists (skipped)")
                success_count += 1
            else:
                print(f"         ✗ Error: {error_str[:100]}")
                error_count += 1

    print("\n" + "=" * 60)
    print(f"Migration complete: {success_count} succeeded, {error_count} failed")
    print("=" * 60)

    return error_count == 0


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
