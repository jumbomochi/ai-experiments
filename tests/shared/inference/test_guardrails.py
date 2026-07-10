"""Unit tests for the inference-layer privacy guardrail."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from shared.eval.runner.preflight import PreflightFailure
from shared.inference.guardrails import enforce_privacy_guardrail


@dataclass(frozen=True)
class FakeManifest:
    target_host: str


def test_tier1_host_allows_private_example() -> None:
    for host in ("mac", "spark", "cloud-burst-l4", "cloud-burst-a2",
                 "cloud-burst-a3", "cloud-burst-p5"):
        manifest = FakeManifest(target_host=host)
        examples = [{"example_id": "ex_1", "never_to_third_party": True}]
        enforce_privacy_guardrail(manifest, examples)  # must not raise


def test_non_tier1_host_with_private_example_raises() -> None:
    manifest = FakeManifest(target_host="openai-gpt4")
    examples = [{"example_id": "ex_secret", "never_to_third_party": True}]
    with pytest.raises(PreflightFailure) as ei:
        enforce_privacy_guardrail(manifest, examples)
    assert ei.value.step == "privacy_violation"
    assert "ex_secret" in str(ei.value)


def test_non_tier1_host_with_public_example_passes() -> None:
    manifest = FakeManifest(target_host="openai-gpt4")
    examples = [{"example_id": "ex_public", "never_to_third_party": False}]
    enforce_privacy_guardrail(manifest, examples)  # must not raise
