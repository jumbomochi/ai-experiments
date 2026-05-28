"""Rate-card-based cost accountant.

Pure function from (usage, wall_ms) → cost_usd. Per spec §1: cost lives in the
runner; the contract is unaware. Rate cards are per `target_host`, loaded from
YAML files under `rate_cards/`.

For each call:
    if usage is present:
        cost = (prompt_tokens × prompt_usd_per_mtok + completion_tokens × completion_usd_per_mtok) / 1e6
               + wall_ms × wall_usd_per_hour / 3_600_000
    else:
        cost = wall_ms × wall_usd_per_hour / 3_600_000     (fallback)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

RATE_CARDS_DIR = Path(__file__).resolve().parent / "rate_cards"


@dataclass(frozen=True)
class RateCard:
    target_host: str
    unit: Literal["per_mtok"]   # only one unit supported in v0.1
    prompt_usd_per_mtok: float
    completion_usd_per_mtok: float
    wall_usd_per_hour: float


def load_rate_card(target_host: str) -> RateCard:
    path = RATE_CARDS_DIR / f"{target_host}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"no rate card for target_host={target_host!r} at {path}"
        )
    raw = yaml.safe_load(path.read_text())
    return RateCard(**raw)


class CostAccountant:
    def __init__(self, rate_card: RateCard) -> None:
        self.rate_card = rate_card

    @classmethod
    def from_rate_card(cls, rate_card: RateCard) -> "CostAccountant":
        return cls(rate_card)

    @classmethod
    def for_target(cls, target_host: str) -> "CostAccountant":
        return cls(load_rate_card(target_host))

    def cost_per_call(
        self,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        wall_ms: int,
    ) -> float:
        wall_cost = wall_ms * self.rate_card.wall_usd_per_hour / 3_600_000
        if prompt_tokens is None or completion_tokens is None:
            return wall_cost
        token_cost = (
            prompt_tokens * self.rate_card.prompt_usd_per_mtok
            + completion_tokens * self.rate_card.completion_usd_per_mtok
        ) / 1_000_000
        return token_cost + wall_cost
