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
    """Execute `call` with backoff retries for retryable/rate-limit errors.

    Re-raises the original exception (with its traceback intact) when:
    - retries are exhausted, OR
    - the exception is neither retryable nor rate-limit.
    """
    for attempt in range(4):  # 1 try + 3 retries
        try:
            return call()
        except Exception as exc:
            if attempt == 3 or (not is_rate_limit(exc) and not is_retryable(exc)):
                raise
            if is_rate_limit(exc):
                wait = retry_after_s(exc) or _RATE_LIMIT_BACKOFFS_S[attempt]
            else:
                wait = _RETRY_BACKOFFS_S[attempt]
            sleep(wait)
    # Unreachable: range(4) means attempt==3 raises above.
    raise RuntimeError("with_retry: loop exited without return or raise")
