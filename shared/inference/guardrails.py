"""Privacy guardrail enforced at the inference boundary.

Tier 1 sovereign hosts (where we control the full runtime and data flow)
are exempt. All other hosts are blocked from receiving examples marked
never_to_third_party.
"""
from __future__ import annotations

from shared.eval.runner.preflight import PreflightFailure
from shared.models.manifest import ModelManifest

_TIER1_HOSTS = frozenset({
    "mac", "spark",
    "cloud-burst-l4", "cloud-burst-a2", "cloud-burst-a3", "cloud-burst-p5",
})


def enforce_privacy_guardrail(manifest: ModelManifest, examples: list[dict]) -> None:
    if manifest.target_host in _TIER1_HOSTS:
        return
    for ex in examples:
        if ex.get("never_to_third_party"):
            raise PreflightFailure(
                "privacy_violation",
                RuntimeError(
                    f"example {ex['example_id']} cannot reach non-Tier-1 host "
                    f"{manifest.target_host}"
                ),
            )
