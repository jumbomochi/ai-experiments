"""Minimal SQL migration applier.

Migrations are plain SQL files under `migrations/`, named `NNN_<slug>.sql` and
applied in lexical order. Applied IDs are recorded in `schema_migrations`.

CLI:  uv run python -m shared.db.migrations apply [--test]
      uv run python -m shared.db.migrations list  [--test]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from shared.db.connection import connect

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
MIGRATION_RE = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


def _ensure_schema_migrations(test: bool = False) -> None:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "id text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )


def applied_migrations(test: bool = False) -> set[str]:
    _ensure_schema_migrations(test=test)
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def _discover() -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = []
    for p in sorted(MIGRATIONS_DIR.iterdir()):
        m = MIGRATION_RE.match(p.name)
        if m:
            entries.append((m.group(1), p))
    return entries


def apply_all(test: bool = False) -> list[str]:
    """Apply every migration not yet recorded; return the list applied this run."""
    applied = applied_migrations(test=test)
    new_ids: list[str] = []
    for mid, path in _discover():
        if mid in applied:
            continue
        sql = path.read_text()
        with connect(test=test) as conn, conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (id) VALUES (%s)", (mid,)
            )
        new_ids.append(mid)
    return new_ids


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["apply", "list"])
    p.add_argument("--test", action="store_true")
    args = p.parse_args()
    if args.cmd == "list":
        applied = applied_migrations(test=args.test)
        for mid, path in _discover():
            mark = "✓" if mid in applied else " "
            print(f"  {mark}  {mid}  {path.name}")
    else:
        new = apply_all(test=args.test)
        if new:
            print("applied:", ", ".join(new))
        else:
            print("nothing to apply")


if __name__ == "__main__":
    _cli()
