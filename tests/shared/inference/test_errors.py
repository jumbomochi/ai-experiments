"""Error-classification tests for the inference client."""
from __future__ import annotations

import pytest

from shared.inference.errors import classify, ErrorClass


@pytest.mark.parametrize(
    "status, expected",
    [
        (500, ErrorClass.RETRYABLE),
        (502, ErrorClass.RETRYABLE),
        (503, ErrorClass.RETRYABLE),
        (504, ErrorClass.RETRYABLE),
        (429, ErrorClass.RATE_LIMIT),
        (400, ErrorClass.CLIENT_FATAL),
        (404, ErrorClass.CLIENT_FATAL),
        (422, ErrorClass.CLIENT_FATAL),
    ],
)
def test_classify_status_codes(status: int, expected: ErrorClass) -> None:
    assert classify(status, body=None) is expected


def test_classify_oom_in_body_is_catastrophic() -> None:
    body = {"error": {"type": "OOM", "message": "CUDA out of memory"}}
    assert classify(500, body=body) is ErrorClass.CATASTROPHIC


def test_classify_malformed_json_is_catastrophic() -> None:
    assert classify(None, body=None, malformed=True) is ErrorClass.CATASTROPHIC
