"""Tests for the gold-set JSONL record schema."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.goldsets.schema import Expected, GoldExample


def test_valid_exact_example_parses() -> None:
    raw = {
        "example_id": "ex_general_001a2b3c",
        "lane": "general",
        "source": "src",
        "annotator": "jonathan",
        "annotated_at": "2026-05-26",
        "prompt_template": "general/multi-choice.j2",
        "inputs": {"question": "q", "choices": {"A": "a", "B": "b"}},
        "expected": {"type": "exact", "value": "A"},
        "provenance_tag": "public",
        "never_to_third_party": False,
        "tags": ["smoke"],
        "contamination_risk": "high",
    }
    ex = GoldExample.model_validate(raw)
    assert ex.expected.type == "exact"
    assert ex.expected.value == "A"


def test_unknown_lane_rejected() -> None:
    with pytest.raises(ValueError, match="lane"):
        GoldExample.model_validate({
            "example_id": "ex_x_001a2b3c",
            "lane": "marsupials",
            "annotator": "x",
            "annotated_at": "2026-05-26",
            "prompt_template": "x.j2",
            "inputs": {},
            "expected": {"type": "exact", "value": "A"},
            "provenance_tag": "public",
            "never_to_third_party": False,
        })


def test_id_format_enforced() -> None:
    with pytest.raises(ValueError, match="example_id"):
        GoldExample.model_validate({
            "example_id": "invalid-id-format",
            "lane": "general",
            "annotator": "x",
            "annotated_at": "2026-05-26",
            "prompt_template": "x.j2",
            "inputs": {},
            "expected": {"type": "exact", "value": "A"},
            "provenance_tag": "public",
            "never_to_third_party": False,
        })


def test_exact_requires_value():
    e = Expected(type="exact", value="Paris")
    assert e.value == "Paris"
    assert e.rubric is None


def test_exact_raises_without_value():
    with pytest.raises(ValidationError, match="value is required"):
        Expected(type="exact", value=None)


def test_set_requires_value():
    e = Expected(type="set", value=["Paris", "Lyon"])
    assert e.value == ["Paris", "Lyon"]


def test_rubric_requires_rubric_field():
    with pytest.raises(ValidationError, match="rubric is required"):
        Expected(type="rubric")


def test_rubric_valid_with_no_reference():
    e = Expected(type="rubric", rubric="Award 1.0 if correct.")
    assert e.rubric == "Award 1.0 if correct."
    assert e.reference is None
    assert e.value is None


def test_rubric_valid_with_reference():
    e = Expected(type="rubric", rubric="Award 1.0 if correct.", reference="Singapore")
    assert e.reference == "Singapore"
