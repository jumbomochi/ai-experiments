"""5-step preflight per spec §5. Step 6 (writing the initial run row) is the
caller's responsibility in runner.py."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from shared.eval.errors import PreflightFailure

__all__ = ["PreflightFailure", "preflight_or_raise"]


def preflight_or_raise(
    check_postgres: Callable[[], None],
    check_manifest: Callable[[], Any],
    check_trust_gate: Callable[[], dict],
    check_rate_card: Callable[[str], None],
    check_endpoint_ready: Callable[[str, float], None],
    endpoint_timeout_s: float = 60.0,
) -> tuple[Any, dict]:
    """Run all five steps in order; on failure raise PreflightFailure with step+cause.

    Returns (manifest, bundle) on success, where bundle is the dict returned by
    check_trust_gate.
    """
    try:
        check_postgres()
    except Exception as e:
        raise PreflightFailure("postgres", e) from e

    try:
        manifest = check_manifest()
    except Exception as e:
        raise PreflightFailure("manifest", e) from e

    try:
        bundle = check_trust_gate()
    except Exception as e:
        raise PreflightFailure("trust_gate", e) from e

    try:
        check_rate_card(manifest.target_host)
    except Exception as e:
        raise PreflightFailure("rate_card", e) from e

    try:
        check_endpoint_ready(manifest.endpoint, endpoint_timeout_s)
    except Exception as e:
        raise PreflightFailure("endpoint_ready", e) from e

    return manifest, bundle
