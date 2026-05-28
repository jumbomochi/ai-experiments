"""Tests for judgement aggregation."""
from __future__ import annotations

import pytest

from shared.eval.judges.aggregate import Judgement, aggregate


def test_single_deterministic_judgement_wins() -> None:
    j = [Judgement(judge_role="deterministic", score=1.0, score_kind="binary")]
    out = aggregate(j, weights={"deterministic": 1.0, "specialist": 0.7})
    assert out == (1.0, "binary")


def test_deterministic_tie_breaks_when_multiple_judges_present() -> None:
    j = [
        Judgement(judge_role="deterministic", score=1.0, score_kind="binary"),
        Judgement(judge_role="specialist", score=0.4, score_kind="scalar"),
    ]
    out = aggregate(j, weights={"deterministic": 1.0, "specialist": 0.7})
    assert out == (1.0, "binary")


def test_weighted_mean_when_no_deterministic() -> None:
    j = [
        Judgement(judge_role="specialist", score=0.8, score_kind="scalar"),
        Judgement(judge_role="generalist", score=0.5, score_kind="scalar"),
    ]
    out = aggregate(j, weights={"specialist": 0.7, "generalist": 0.3})
    assert out[0] == pytest.approx((0.8 * 0.7 + 0.5 * 0.3) / 1.0, rel=1e-6)
    assert out[1] == "rubric_aggregate"


def test_parse_errors_excluded_from_aggregation() -> None:
    j = [
        Judgement(judge_role="specialist", score=None, score_kind="scalar", parse_error=True),
        Judgement(judge_role="generalist", score=0.5, score_kind="scalar"),
    ]
    out = aggregate(j, weights={"specialist": 0.7, "generalist": 0.3})
    assert out[0] == pytest.approx(0.5, rel=1e-6)
