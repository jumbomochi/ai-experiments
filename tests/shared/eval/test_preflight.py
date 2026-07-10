"""Tests for the 5-step preflight."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from shared.eval.runner.preflight import PreflightFailure, preflight_or_raise


@dataclass(frozen=True)
class FakeManifest:
    target_host: str = "mac"
    endpoint: str = "http://localhost:11434/v1"


def test_passes_when_all_steps_ok() -> None:
    fake_bundle = {"trust": {"enforcement": "lenient"}}
    manifest, bundle = preflight_or_raise(
        check_postgres=lambda: None,
        check_manifest=lambda: FakeManifest(),
        check_trust_gate=lambda: fake_bundle,
        check_rate_card=lambda h: None,
        check_endpoint_ready=lambda url, timeout_s: None,
    )
    assert isinstance(manifest, FakeManifest)
    assert bundle == fake_bundle


def test_fails_at_postgres_step() -> None:
    def boom():
        raise RuntimeError("connection refused")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=boom,
            check_manifest=lambda: FakeManifest(),
            check_trust_gate=lambda: {},
            check_rate_card=lambda h: None,
            check_endpoint_ready=lambda url, timeout_s: None,
        )
    assert ei.value.step == "postgres"


def test_fails_at_rate_card_step() -> None:
    def no_card(host):
        raise FileNotFoundError(f"no rate card for {host}")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=lambda: None,
            check_manifest=lambda: FakeManifest(),
            check_trust_gate=lambda: {},
            check_rate_card=no_card,
            check_endpoint_ready=lambda url, timeout_s: None,
        )
    assert ei.value.step == "rate_card"


def test_fails_at_manifest_step() -> None:
    def boom():
        raise KeyError("no such model_id")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=lambda: None,
            check_manifest=boom,
            check_trust_gate=lambda: {},
            check_rate_card=lambda h: None,
            check_endpoint_ready=lambda url, timeout_s: None,
        )
    assert ei.value.step == "manifest"


def test_fails_at_trust_gate_step() -> None:
    def boom():
        raise NotImplementedError("strict trust gate not implemented")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=lambda: None,
            check_manifest=lambda: FakeManifest(),
            check_trust_gate=boom,
            check_rate_card=lambda h: None,
            check_endpoint_ready=lambda url, timeout_s: None,
        )
    assert ei.value.step == "trust_gate"


def test_fails_at_endpoint_ready_step() -> None:
    def boom(url, timeout_s):
        raise TimeoutError(f"endpoint {url} not ready within {timeout_s}s")

    with pytest.raises(PreflightFailure) as ei:
        preflight_or_raise(
            check_postgres=lambda: None,
            check_manifest=lambda: FakeManifest(),
            check_trust_gate=lambda: {},
            check_rate_card=lambda h: None,
            check_endpoint_ready=boom,
        )
    assert ei.value.step == "endpoint_ready"
