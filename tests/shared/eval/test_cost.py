"""Tests for the cost accountant."""
from __future__ import annotations

import pytest

from shared.eval.cost.accountant import CostAccountant, RateCard, load_rate_card


def test_per_token_cost_calculation() -> None:
    rc = RateCard(
        target_host="mac",
        unit="per_mtok",
        prompt_usd_per_mtok=0.0,
        completion_usd_per_mtok=0.0,
        wall_usd_per_hour=0.05,
    )
    cost = CostAccountant.from_rate_card(rc).cost_per_call(
        prompt_tokens=1_000, completion_tokens=500, wall_ms=400
    )
    # Mac mini is free-per-token (amortized) but bill 0.05 USD/hour wall time → 400ms → 0.05 * (0.4/3600).
    assert cost == pytest.approx(0.05 * 0.4 / 3600, rel=1e-6)


def test_per_mtok_cost_calculation() -> None:
    rc = RateCard(
        target_host="tier2-fireworks",
        unit="per_mtok",
        prompt_usd_per_mtok=0.20,
        completion_usd_per_mtok=0.60,
        wall_usd_per_hour=0.0,
    )
    cost = CostAccountant.from_rate_card(rc).cost_per_call(
        prompt_tokens=1_000_000, completion_tokens=500_000, wall_ms=10_000
    )
    assert cost == pytest.approx(0.20 + 0.30, rel=1e-6)


def test_missing_usage_falls_back_to_wall_time() -> None:
    rc = RateCard(
        target_host="mac",
        unit="per_mtok",
        prompt_usd_per_mtok=0.10,
        completion_usd_per_mtok=0.10,
        wall_usd_per_hour=0.05,
    )
    cost = CostAccountant.from_rate_card(rc).cost_per_call(
        prompt_tokens=None, completion_tokens=None, wall_ms=3_600_000
    )
    assert cost == pytest.approx(0.05, rel=1e-6)


def test_load_rate_card_for_mac_matches_manifest_target_host() -> None:
    """load_rate_card('mac') must find rate_cards/mac.yaml — the filename
    convention matches the target_host on the model manifest, so the runner
    can resolve a manifest → rate card with one lookup."""
    rc = load_rate_card("mac")
    assert rc.target_host == "mac"
    assert rc.unit == "per_mtok"
    assert rc.wall_usd_per_hour == 0.05


def test_load_rate_card_missing_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError, match="no rate card"):
        load_rate_card("no-such-target")
