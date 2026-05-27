"""Tests for the Postgres-sync side of the model registry."""
from __future__ import annotations

import textwrap
from pathlib import Path

from shared.db.connection import connect
from shared.db.migrations import apply_all
from shared.models.manifest import load_manifest_yaml
from shared.models.registry import sync_to_postgres, resolve


def _reset_test_db() -> None:
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    apply_all(test=True)


def _write_manifest(path: Path) -> Path:
    path.write_text(textwrap.dedent("""\
        id: qwen2.5-0.5b-instruct-ollama
        family: qwen2.5
        size: 0.5b
        revision: "2024-09-19"
        runtime: ollama
        runtime_version: "0.3.12"
        target_host: mac
        endpoint: "http://localhost:11434/v1"
        capabilities: [chat]
        context_window: 32768
        default_sampling: {temperature: 0.0, top_p: 1.0, max_tokens: 256}
    """))
    return path


def test_sync_to_postgres_inserts_row(tmp_path: Path) -> None:
    _reset_test_db()
    yaml_path = _write_manifest(tmp_path / "m.yaml")
    m = load_manifest_yaml(yaml_path)
    sync_to_postgres([m], test=True)
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, runtime FROM model_manifest")
        rows = cur.fetchall()
    assert rows == [("qwen2.5-0.5b-instruct-ollama", "ollama")]


def test_resolve_returns_manifest_by_id(tmp_path: Path) -> None:
    _reset_test_db()
    yaml_path = _write_manifest(tmp_path / "m.yaml")
    sync_to_postgres([load_manifest_yaml(yaml_path)], test=True)
    m = resolve("qwen2.5-0.5b-instruct-ollama", test=True)
    assert m.runtime == "ollama"
    assert m.endpoint.endswith("/v1")
