"""Aggregation rule (spec §4): deterministic tie-break, else weighted mean."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Judgement:
    judge_role: str         # deterministic | specialist | generalist | ...
    score: float | None     # None if parse_error
    score_kind: str         # binary | scalar | rubric_aggregate
    parse_error: bool = False


def aggregate(
    judgements: list[Judgement],
    weights: dict[str, float],
) -> tuple[float, str]:
    """Return (aggregated_score, score_kind).

    Raises ValueError if no usable judgement remains after excluding parse errors.
    """
    usable = [j for j in judgements if not j.parse_error and j.score is not None]
    if not usable:
        raise ValueError("no usable judgements after excluding parse errors")

    # Deterministic tie-break
    for j in usable:
        if j.judge_role == "deterministic":
            return float(j.score), j.score_kind

    # Otherwise weighted mean
    num = sum(j.score * weights.get(j.judge_role, 0.0) for j in usable)
    den = sum(weights.get(j.judge_role, 0.0) for j in usable)
    if den == 0:
        raise ValueError(f"no positive weights for any judge_role in {[j.judge_role for j in usable]}")
    return num / den, "rubric_aggregate"
