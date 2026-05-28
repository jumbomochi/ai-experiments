"""Tests for the JSONL → Postgres loader (idempotency + immutability)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.db.connection import connect
from shared.db.migrations import apply_all
from shared.goldsets.loader import load_jsonl_to_postgres


def _reset_test_db() -> None:
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    apply_all(test=True)


SEED = [
    {"example_id": "ex_general_seed0001", "lane": "general",
     "source": "x", "annotator": "j", "annotated_at": "2026-05-26",
     "prompt_template": "general/multi-choice.j2",
     "inputs": {"question": "q", "choices": {"A": "a", "B": "b"}},
     "expected": {"type": "exact", "value": "A"},
     "provenance_tag": "public", "never_to_third_party": False,
     "tags": ["smoke"], "contamination_risk": "high"}
]


def _write_seed(p: Path) -> None:
    with p.open("w") as f:
        for rec in SEED:
            f.write(json.dumps(rec) + "\n")


def test_load_writes_one_version_and_one_example(tmp_path: Path) -> None:
    _reset_test_db()
    p = tmp_path / "seed.jsonl"
    _write_seed(p)
    load_jsonl_to_postgres(p, "v0.1", "abc123", test=True)
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT version, released FROM gold_set_version")
        assert cur.fetchall() == [("v0.1", True)]
        cur.execute("SELECT count(*) FROM gold_example")
        assert cur.fetchone() == (1,)


def test_load_is_idempotent_on_same_sha(tmp_path: Path) -> None:
    _reset_test_db()
    p = tmp_path / "seed.jsonl"
    _write_seed(p)
    load_jsonl_to_postgres(p, "v0.1", "abc123", test=True)
    load_jsonl_to_postgres(p, "v0.1", "abc123", test=True)  # second call no-op
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM gold_example")
        assert cur.fetchone() == (1,)


def test_load_rejects_same_version_different_sha(tmp_path: Path) -> None:
    _reset_test_db()
    p = tmp_path / "seed.jsonl"
    _write_seed(p)
    load_jsonl_to_postgres(p, "v0.1", "abc123", test=True)
    with pytest.raises(ValueError, match="immutability"):
        load_jsonl_to_postgres(p, "v0.1", "def456", test=True)


def test_load_raises_on_invalid_json_with_position(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    p.write_text(
        json.dumps(SEED[0]) + "\n"
        "this-is-not-json\n"
    )
    with pytest.raises(ValueError, match=rf"{p}:2: invalid JSON"):
        load_jsonl_to_postgres(p, "v0.1", "abc", test=True)


def test_load_raises_on_schema_violation_with_position(tmp_path: Path) -> None:
    p = tmp_path / "bad-schema.jsonl"
    # Second record is missing the required `lane` field.
    bad = dict(SEED[0])
    bad.pop("lane")
    p.write_text(
        json.dumps(SEED[0]) + "\n"
        + json.dumps(bad) + "\n"
    )
    with pytest.raises(ValueError, match=rf"{p}:2: schema validation failed"):
        load_jsonl_to_postgres(p, "v0.1", "abc", test=True)


def test_load_rejects_empty_jsonl(tmp_path: Path) -> None:
    _reset_test_db()
    p = tmp_path / "empty.jsonl"
    p.write_text("")
    with pytest.raises(ValueError, match="no valid examples"):
        load_jsonl_to_postgres(p, "v0.1", "abc", test=True)
    # Critically: confirm no gold_set_version row was inserted.
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM gold_set_version")
        assert cur.fetchone() == (0,)
