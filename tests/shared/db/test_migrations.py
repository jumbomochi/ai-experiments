"""Tests for the migration applier."""
from __future__ import annotations

import psycopg

from shared.db.connection import connect
from shared.db.migrations import apply_all, applied_migrations


def _reset_test_db() -> None:
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


def test_apply_all_creates_schema_migrations_and_seven_tables() -> None:
    _reset_test_db()
    apply_all(test=True)
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname='public' ORDER BY tablename"
        )
        tables = {row[0] for row in cur.fetchall()}
    expected = {
        "schema_migrations",
        "model_manifest",
        "gold_set_version",
        "gold_example",
        "judge_config",
        "run",
        "result",
        "judgement",
    }
    assert tables == expected, f"unexpected tables: {tables ^ expected}"


def test_apply_all_is_idempotent() -> None:
    _reset_test_db()
    apply_all(test=True)
    first = applied_migrations(test=True)
    apply_all(test=True)  # second apply
    second = applied_migrations(test=True)
    assert first == second
