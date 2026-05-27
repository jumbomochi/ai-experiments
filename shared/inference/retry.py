"""Exponential backoff loop for retryable errors."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

# Spec §1: 3 retries with backoff 1s / 4s / 16s for retryable; 10/30/60s for rate-limit.
_RETRY_BACKOFFS_S = (1, 4, 16)
_RATE_LIMIT_BACKOFFS_S = (10, 30, 60)


def with_retry(
    call: Callable[[], T],
    is_retryable: Callable[[Exception], bool],
    is_rate_limit: Callable[[Exception], bool] = lambda _: False,
    retry_after_s: Callable[[Exception], float | None] = lambda _: None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Execute `call` with backoff retries for retryable/rate-limit errors."""
    last_exc: Exception | None = None
    for attempt in range(4):  # 1 try + 3 retries
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 — caller classifies
            last_exc = exc
            if attempt == 3:
                break
            if is_rate_limit(exc):
                wait = retry_after_s(exc) or _RATE_LIMIT_BACKOFFS_S[attempt]
            elif is_retryable(exc):
                wait = _RETRY_BACKOFFS_S[attempt]
            else:
                raise
            sleep(wait)
    assert last_exc is not None
    raise last_exc
