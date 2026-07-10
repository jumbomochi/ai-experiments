"""Tests for argilla_export — uses a mocked argilla client."""
from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_record(
    record_id: str,
    expected_type: str = "exact",
    expected_value: str = "Paris",
    status: str = "submitted",
) -> MagicMock:
    answer_map = {
        "expected_type": MagicMock(value=expected_type),
        "expected_value": MagicMock(value=expected_value),
        "never_to_third_party": MagicMock(value="false"),
        "contamination_risk": MagicMock(value="none"),
    }
    response = MagicMock()
    response.status = status
    response.answers = answer_map
    record = MagicMock()
    record.id = record_id
    record.responses = {"user1": response}
    record.updated_at = datetime(2026, 7, 11, tzinfo=timezone.utc)
    return record


def _mock_argilla(records: list) -> MagicMock:
    dataset = MagicMock()
    dataset.records.return_value = iter(records)
    client = MagicMock()
    client.datasets.return_value = dataset
    return client


def test_export_exact_type(tmp_path):
    from shared.goldsets.argilla_export import export_lane

    # Write a seed JSONL so export_lane can re-join inputs
    seed_file = tmp_path / "seed.jsonl"
    seed_file.write_text(json.dumps({
        "example_id": "ex_general_001",
        "lane": "general",
        "annotator": "huiliang",
        "annotated_at": "2026-07-11",
        "prompt_template": "qa",
        "inputs": {"question": "What is the capital of France?"},
        "provenance_tag": "public",
        "never_to_third_party": False,
        "tags": ["smoke"],
        "contamination_risk": "none",
    }) + "\n")

    record = _make_record("ex_general_001", "exact", "Paris", status="submitted")
    out_file = tmp_path / "annotated.jsonl"

    with patch("shared.goldsets.argilla_export.rg.Argilla",
               return_value=_mock_argilla([record])):
        n = export_lane("general", out_file, "http://localhost:6900", "key", seed_path=seed_file)

    assert n == 1
    rows = [json.loads(l) for l in out_file.read_text().strip().splitlines()]
    assert len(rows) == 1
    assert rows[0]["expected"] == {"type": "exact", "value": "Paris"}
    assert rows[0]["inputs"] == {"question": "What is the capital of France?"}


def test_export_skips_pending_records(tmp_path):
    from shared.goldsets.argilla_export import export_lane

    seed_file = tmp_path / "seed.jsonl"
    seed_file.write_text(json.dumps({
        "example_id": "ex_general_001",
        "lane": "general",
        "annotator": "huiliang",
        "annotated_at": "2026-07-11",
        "prompt_template": "qa",
        "inputs": {"question": "Q?"},
        "provenance_tag": "public",
        "never_to_third_party": False,
        "tags": [],
        "contamination_risk": "none",
    }) + "\n")

    submitted = _make_record("ex_general_001", "exact", "Paris", status="submitted")
    pending = _make_record("ex_general_002", "exact", "Lyon", status="pending")
    out_file = tmp_path / "annotated.jsonl"

    with patch("shared.goldsets.argilla_export.rg.Argilla",
               return_value=_mock_argilla([submitted, pending])):
        n = export_lane("general", out_file, "http://localhost:6900", "key", seed_path=seed_file)

    assert n == 1  # only the submitted record exported
    rows = [json.loads(l) for l in out_file.read_text().strip().splitlines()]
    assert len(rows) == 1
    assert rows[0]["example_id"] == "ex_general_001"


def test_export_rubric_type_builds_correct_expected():
    """_build_expected_from_answers returns correct rubric expected dict."""
    from shared.goldsets.argilla_export import _build_expected_from_answers

    answers = {
        "expected_type": "rubric",
        "expected_value": "Award 1.0 if correct.",
        "reference_answer": "Singapore",
    }
    result = _build_expected_from_answers(answers)
    assert result == {
        "type": "rubric",
        "rubric": "Award 1.0 if correct.",
        "reference": "Singapore",
    }


def test_export_rubric_no_reference():
    from shared.goldsets.argilla_export import _build_expected_from_answers

    answers = {
        "expected_type": "rubric",
        "expected_value": "Award 1.0 if correct.",
        "reference_answer": "",
    }
    result = _build_expected_from_answers(answers)
    assert result["reference"] is None
