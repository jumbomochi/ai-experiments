"""Unit tests for _lm_judge_score helper."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from shared.eval.runner.runner import _lm_judge_score
from shared.goldsets.schema import Expected

_RUBRIC_TEMPLATE = """\
You are a strict evaluator. Score the response below using the rubric.

### Question
{{ question }}

### Response
{{ response }}

{% if reference %}### Reference answer
{{ reference }}
{% endif %}

### Rubric
{{ rubric }}

Reply in this exact format:
SCORE: <number between 0.0 and 1.0>
RATIONALE: <one sentence>
"""

_BUNDLE = {
    "judges": {
        "lm_judge": {
            "model_id": "Qwen/Qwen2.5-72B-Instruct-AWQ",
            "endpoint": "http://127.0.0.1:8000/v1",
            "rubric_template": _RUBRIC_TEMPLATE,
            "max_tokens": 128,
            "temperature": 0.0,
        }
    },
    "aggregation": {"weights": {"lm_judge": 1.0}},
    "trust": {"enforcement": "lenient"},
}


def _make_resp(content: str, prompt_tokens: int = 50, completion_tokens: int = 20) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.usage.prompt_tokens = prompt_tokens
    resp.usage.completion_tokens = completion_tokens
    return resp


def _mock_judge_factory(resp: MagicMock):
    def factory(cfg):  # noqa: ARG001
        client = MagicMock()
        client.chat.return_value = resp
        return client
    return factory


def test_happy_path_with_reference():
    expected = Expected(type="rubric", rubric="Award 1.0 if correct.", reference="Singapore")
    resp = _make_resp("SCORE: 0.9\nRATIONALE: The answer correctly identifies Singapore.")

    result = _lm_judge_score(
        "What is the richest SEA country?", "Singapore", expected, _BUNDLE,
        judge_client_factory=_mock_judge_factory(resp),
    )

    assert result.judge_role == "lm_judge"
    assert result.score == pytest.approx(0.9)
    assert result.parse_error is False
    assert result.rationale == "The answer correctly identifies Singapore."
    assert result.raw_response is not None
    assert result.rendered_prompt is not None
    assert "Singapore" in result.rendered_prompt  # reference rendered into prompt


def test_parse_failure_returns_parse_error():
    expected = Expected(type="rubric", rubric="Award 1.0 if correct.")
    resp = _make_resp("I think the answer is pretty good overall.")  # no SCORE: line

    result = _lm_judge_score(
        "Q", "A", expected, _BUNDLE,
        judge_client_factory=_mock_judge_factory(resp),
    )

    assert result.parse_error is True
    assert result.score is None
    assert result.judge_role == "lm_judge"


def test_no_reference_field_renders_cleanly():
    expected = Expected(type="rubric", rubric="Award 1.0 if the answer mentions GDP.")
    resp = _make_resp("SCORE: 0.5\nRATIONALE: Partial answer.")

    result = _lm_judge_score(
        "Q", "A", expected, _BUNDLE,
        judge_client_factory=_mock_judge_factory(resp),
    )

    assert result.score == pytest.approx(0.5)
    assert result.parse_error is False
    assert result.rendered_prompt is not None
    assert "Reference answer" not in result.rendered_prompt  # no reference block


def test_score_clamped_to_unit_interval():
    expected = Expected(type="rubric", rubric="Score between 0 and 1.")
    resp = _make_resp("SCORE: 1.5\nRATIONALE: Exceeded rubric ceiling.")

    result = _lm_judge_score(
        "Q", "A", expected, _BUNDLE,
        judge_client_factory=_mock_judge_factory(resp),
    )

    assert result.score == pytest.approx(1.0)  # clamped
