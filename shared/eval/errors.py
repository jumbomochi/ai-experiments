"""Shared exceptions for the eval substrate."""
from __future__ import annotations


class PreflightFailure(RuntimeError):
    def __init__(self, step: str, cause: Exception) -> None:
        super().__init__(f"preflight failed at step={step!r}: {cause}")
        self.step = step
        self.cause = cause
