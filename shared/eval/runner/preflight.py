"""6-step preflight per spec §5."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class PreflightFailure(RuntimeError):
    def __init__(self, step: str, cause: Exception) -> None:
        super().__init__(f"preflight failed at step={step!r}: {cause}")
        self.step = step
        self.cause = cause


@dataclass(frozen=True)
class PreflightHooks:
    check_postgres: Callable[[], None]
    check_manifest: Callable[[], Any]      # returns the resolved manifest
    check_trust_gate: Callable[[], None]
    check_rate_card: Callable[[str], None] # given target_host
    check_endpoint_ready: Callable[[str, float], None]  # url, timeout_s


def preflight_or_raise(
    check_postgres: Callable[[], None],
    check_manifest: Callable[[], Any],
    check_trust_gate: Callable[[], None],
    check_rate_card: Callable[[str], None],
    check_endpoint_ready: Callable[[str, float], None],
    endpoint_timeout_s: float = 60.0,
) -> Any:
    """Run all six steps in order; on failure raise PreflightFailure with step+cause.

    Returns the resolved manifest on success.
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
        check_trust_gate()
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

    return manifest
