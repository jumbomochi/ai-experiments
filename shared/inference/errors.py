"""Error classification for the inference client.

Four buckets, per spec §1:
- RETRYABLE: 5xx-class server errors, connection errors → exponential backoff
- RATE_LIMIT: 429 → backoff with Retry-After honor
- CLIENT_FATAL: 4xx where retry won't help → fail this example, continue campaign
- CATASTROPHIC: unrecoverable (OOM-in-body, malformed JSON, repeated 5xx) → halt campaign
"""
from __future__ import annotations

import enum
from typing import Mapping, Any


class ErrorClass(str, enum.Enum):
    RETRYABLE = "retryable"
    RATE_LIMIT = "rate_limit"
    CLIENT_FATAL = "client_fatal"
    CATASTROPHIC = "catastrophic"


class InferenceError(Exception):
    def __init__(self, msg: str, error_class: ErrorClass, status: int | None,
                 body: Any | None) -> None:
        super().__init__(msg)
        self.error_class = error_class
        self.status = status
        self.body = body


_OOM_TOKENS = ("OOM", "out of memory", "CUDA out of memory")


def classify(
    status: int | None,
    body: Mapping[str, Any] | None,
    malformed: bool = False,
) -> ErrorClass:
    if malformed:
        return ErrorClass.CATASTROPHIC
    if body is not None:
        msg = str(body.get("error", {}).get("message", "")) if isinstance(body, dict) else ""
        if any(token in msg for token in _OOM_TOKENS):
            return ErrorClass.CATASTROPHIC
    if status is None:
        return ErrorClass.CATASTROPHIC
    if status == 429:
        return ErrorClass.RATE_LIMIT
    if 500 <= status < 600:
        return ErrorClass.RETRYABLE
    if 400 <= status < 500:
        return ErrorClass.CLIENT_FATAL
    raise ValueError(f"unexpected status: {status}")
