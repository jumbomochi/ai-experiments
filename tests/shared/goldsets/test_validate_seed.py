"""Tests for validate_seed — validates seed JSONL against SeedExample schema."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from shared.goldsets.validate_seed import validate_seed


def _write_jsonl(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "seed.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    return p


_VALID_ROW = {
    "example_id": "ex_general_001",
    "lane": "general",
    "annotator": "huiliang",
    "annotated_at": "2026-07-11",
    "prompt_template": "qa",
    "inputs": {"question": "What is the capital of France?"},
}


def test_validate_seed_passes_valid_file(tmp_path):
    path = _write_jsonl(tmp_path, [_VALID_ROW])
    errors = validate_seed(path)
    assert errors == []


def test_validate_seed_catches_bad_id(tmp_path):
    row = {**_VALID_ROW, "example_id": "bad-format"}
    path = _write_jsonl(tmp_path, [row])
    errors = validate_seed(path)
    assert len(errors) == 1
    assert "example_id" in errors[0]


def test_validate_seed_catches_bad_lane(tmp_path):
    row = {**_VALID_ROW, "example_id": "ex_general_002", "lane": "unknown"}
    path = _write_jsonl(tmp_path, [row])
    errors = validate_seed(path)
    assert len(errors) == 1
    assert "lane" in errors[0]


def test_validate_seed_empty_file_is_error(tmp_path):
    path = tmp_path / "seed.jsonl"
    path.write_text("")
    errors = validate_seed(path)
    assert len(errors) == 1
    assert "empty" in errors[0].lower()


def test_validate_seed_reports_all_errors(tmp_path):
    rows = [
        {**_VALID_ROW, "example_id": "bad-1"},
        {**_VALID_ROW, "example_id": "ex_general_002"},  # valid
        {**_VALID_ROW, "example_id": "bad-3"},
    ]
    path = _write_jsonl(tmp_path, rows)
    errors = validate_seed(path)
    assert len(errors) == 2
