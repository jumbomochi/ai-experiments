"""InferenceClient happy-path and error-path tests (HTTP layer mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.inference.client import InferenceClient, ChatRequest, Message
from shared.inference.errors import ErrorClass, InferenceError


@patch("shared.inference.client.requests.post")
def test_chat_completion_happy_path(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "id": "chatcmpl-x",
        "choices": [{"message": {"role": "assistant", "content": "hi"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
    }
    client = InferenceClient(endpoint="http://x:8000/v1", model="m1", timeout_s=10)
    resp = client.chat(ChatRequest(messages=[Message(role="user", content="hi")],
                                   temperature=0.0, top_p=1.0, max_tokens=8))
    assert resp.content == "hi"
    assert resp.usage.prompt_tokens == 5
    assert resp.usage.completion_tokens == 1


@patch("shared.inference.client.requests.post")
def test_chat_completion_4xx_raises_client_fatal(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 400
    mock_post.return_value.json.return_value = {
        "error": {"type": "invalid_request", "message": "bad input"}
    }
    client = InferenceClient(endpoint="http://x:8000/v1", model="m1", timeout_s=10)
    with pytest.raises(InferenceError) as ei:
        client.chat(ChatRequest(messages=[Message(role="user", content="x")],
                                temperature=0.0, top_p=1.0, max_tokens=8))
    assert ei.value.error_class is ErrorClass.CLIENT_FATAL


@patch("shared.inference.client.time.sleep")
@patch("shared.inference.client.requests.post")
def test_chat_completion_retries_then_succeeds(
    mock_post: MagicMock, mock_sleep: MagicMock
) -> None:
    # first two attempts return 503, third returns 200
    mock_post.side_effect = [
        MagicMock(status_code=503, json=MagicMock(return_value={"error": {"message": "tmp"}})),
        MagicMock(status_code=503, json=MagicMock(return_value={"error": {"message": "tmp"}})),
        MagicMock(status_code=200, json=MagicMock(return_value={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })),
    ]
    client = InferenceClient(endpoint="http://x:8000/v1", model="m1", timeout_s=10)
    resp = client.chat(ChatRequest(messages=[Message(role="user", content="x")],
                                   temperature=0.0, top_p=1.0, max_tokens=8))
    assert resp.content == "ok"
    assert mock_sleep.call_count == 2


@patch("shared.inference.client.requests.post")
def test_chat_completion_malformed_200_body_is_catastrophic(mock_post: MagicMock) -> None:
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"id": "x"}  # no `choices`
    client = InferenceClient(endpoint="http://x:8000/v1", model="m1", timeout_s=10)
    with pytest.raises(InferenceError) as ei:
        client.chat(ChatRequest(messages=[Message(role="user", content="x")],
                                temperature=0.0, top_p=1.0, max_tokens=8))
    assert ei.value.error_class is ErrorClass.CATASTROPHIC


@patch("shared.inference.client.time.sleep")
@patch("shared.inference.client.requests.post")
def test_chat_completion_429_honors_retry_after_header(
    mock_post: MagicMock, mock_sleep: MagicMock
) -> None:
    rate_limited = MagicMock(status_code=429,
                              json=MagicMock(return_value={"error": {"message": "slow down"}}),
                              headers={"Retry-After": "7"})
    ok = MagicMock(status_code=200,
                   json=MagicMock(return_value={
                       "choices": [{"message": {"content": "ok"}}],
                       "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                   }))
    mock_post.side_effect = [rate_limited, ok]
    client = InferenceClient(endpoint="http://x:8000/v1", model="m1", timeout_s=10)
    resp = client.chat(ChatRequest(messages=[Message(role="user", content="x")],
                                   temperature=0.0, top_p=1.0, max_tokens=8))
    assert resp.content == "ok"
    # Slept exactly once for the value from the Retry-After header (7s), not the default 10s.
    mock_sleep.assert_called_once_with(7)
