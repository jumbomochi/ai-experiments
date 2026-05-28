"""Tests for the deterministic judge (exact + set matching with normalization)."""
from __future__ import annotations

import pytest

from shared.eval.judges.deterministic import score, DeterministicConfig
from shared.goldsets.schema import Expected


@pytest.fixture
def cfg() -> DeterministicConfig:
    return DeterministicConfig(
        string_normalize=["lowercase", "strip_punct", "whitespace_collapse"],
        numeric_tolerance_abs=1e-6,
        numeric_tolerance_rel=1e-3,
    )


def test_exact_string_match_after_normalization(cfg: DeterministicConfig) -> None:
    assert score(response="  B.", expected=Expected(type="exact", value="B"), cfg=cfg) == 1.0
    assert score(response="b", expected=Expected(type="exact", value="B"), cfg=cfg) == 1.0
    assert score(response="C", expected=Expected(type="exact", value="B"), cfg=cfg) == 0.0


def test_exact_numeric_match_within_tolerance(cfg: DeterministicConfig) -> None:
    assert score(response="3.14159", expected=Expected(type="exact", value=3.14159), cfg=cfg) == 1.0
    assert score(response="3.142", expected=Expected(type="exact", value=3.14159), cfg=cfg) == 1.0
    assert score(response="3.0", expected=Expected(type="exact", value=3.14159), cfg=cfg) == 0.0


def test_set_match_uses_f1(cfg: DeterministicConfig) -> None:
    # Two of three correct + one extra → precision 2/3, recall 2/3 → F1 = 2/3
    result = score(
        response="apple, banana, durian",
        expected=Expected(type="set", value=["apple", "banana", "cherry"]),
        cfg=cfg,
    )
    assert result == pytest.approx(2 / 3, rel=1e-3)


def test_unsupported_expected_type_raises(cfg: DeterministicConfig) -> None:
    with pytest.raises(ValueError, match="rubric"):
        score(response="x", expected=Expected(type="rubric", value={"rubric_id": "r"}), cfg=cfg)


def test_exact_numeric_target_zero(cfg: DeterministicConfig) -> None:
    """At target==0 the relative-tolerance branch must not fire — only abs_tol counts.
    The pre-fix `denom=1.0` fallback silently turned rel_tol into a second, weaker
    abs threshold; the fix returns 0.0 when abs_tol fails on a zero target."""
    assert score(response="0.0", expected=Expected(type="exact", value=0.0), cfg=cfg) == 1.0
    assert score(response="0.0005", expected=Expected(type="exact", value=0.0), cfg=cfg) == 0.0


def test_set_both_empty_returns_one(cfg: DeterministicConfig) -> None:
    """Vacuous-match: empty response, empty expected → perfect (1.0)."""
    assert score(response="", expected=Expected(type="set", value=[]), cfg=cfg) == 1.0
