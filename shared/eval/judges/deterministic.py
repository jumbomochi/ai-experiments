"""Deterministic scorer for `expected.type ∈ {exact, set}`.

Normalization (configured per bundle): lowercase / strip_punct / whitespace_collapse.
Numeric comparison: absolute or relative tolerance.
Set comparison: F1 between predicted set (parsed from comma-separated response)
and expected set.

For `expected.type == "rubric"`, this scorer raises — rubric routing goes
through the specialist judge (Phase 3).
"""
from __future__ import annotations

import re
import string
from dataclasses import dataclass

from shared.goldsets.schema import Expected


@dataclass(frozen=True)
class DeterministicConfig:
    string_normalize: list[str]    # subset of {"lowercase", "strip_punct", "whitespace_collapse"}
    numeric_tolerance_abs: float
    numeric_tolerance_rel: float


_PUNCT_RE = re.compile(rf"[{re.escape(string.punctuation)}]")
_WS_RE = re.compile(r"\s+")


def _normalize(s: str, ops: list[str]) -> str:
    if "lowercase" in ops:
        s = s.lower()
    if "strip_punct" in ops:
        s = _PUNCT_RE.sub("", s)
    if "whitespace_collapse" in ops:
        s = _WS_RE.sub(" ", s).strip()
    return s


def _try_float(s: str) -> float | None:
    try:
        return float(s.strip())
    except (ValueError, AttributeError):
        return None


def score(response: str, expected: Expected, cfg: DeterministicConfig) -> float:
    if expected.type == "rubric":
        raise ValueError("deterministic scorer cannot handle rubric type; route to specialist")

    if expected.type == "exact":
        # Numeric path
        if isinstance(expected.value, (int, float)):
            pred = _try_float(response)
            if pred is None:
                return 0.0
            target = float(expected.value)
            if abs(pred - target) <= cfg.numeric_tolerance_abs:
                return 1.0
            denom = abs(target) if target != 0 else 1.0
            return 1.0 if abs(pred - target) / denom <= cfg.numeric_tolerance_rel else 0.0
        # String path
        return 1.0 if _normalize(response, cfg.string_normalize) == \
                      _normalize(str(expected.value), cfg.string_normalize) else 0.0

    if expected.type == "set":
        expected_set = {_normalize(str(x), cfg.string_normalize) for x in expected.value}
        predicted_raw = [t.strip() for t in str(response).split(",") if t.strip()]
        predicted_set = {_normalize(t, cfg.string_normalize) for t in predicted_raw}
        if not predicted_set and not expected_set:
            return 1.0
        tp = len(predicted_set & expected_set)
        precision = tp / len(predicted_set) if predicted_set else 0.0
        recall = tp / len(expected_set) if expected_set else 0.0
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    raise ValueError(f"unsupported expected.type: {expected.type}")
