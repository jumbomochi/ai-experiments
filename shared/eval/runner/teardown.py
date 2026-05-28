"""Teardown hook abstract base + LocalTeardownHook (no-op for Mac always-on).

Cloud-burst targets in S2+ subclass this and implement actual teardown.
"""
from __future__ import annotations

from typing import Protocol


class TeardownHook(Protocol):
    def teardown(self, reason: str) -> dict:
        """Teardown any on-demand compute. Return a receipt dict (may be empty)."""
        ...


class LocalTeardownHook:
    """No-op teardown for always-on targets (Mac, Spark)."""

    def teardown(self, reason: str) -> dict:
        return {"target": "local", "action": "noop", "reason": reason}
