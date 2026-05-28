"""Eval runner: preflight, campaign loop, teardown hook."""

from shared.eval.runner.runner import run_campaign, RunResult
from shared.eval.runner.preflight import preflight_or_raise, PreflightFailure
from shared.eval.runner.teardown import TeardownHook, LocalTeardownHook

__all__ = [
    "run_campaign",
    "RunResult",
    "preflight_or_raise",
    "PreflightFailure",
    "TeardownHook",
    "LocalTeardownHook",
]
