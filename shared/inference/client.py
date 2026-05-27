"""OpenAI-compatible inference client.

Single class: `InferenceClient(endpoint, model, timeout_s)`. Two methods:
`chat()` and `embeddings()`. Errors classified per `shared.inference.errors`.

Per spec §1: non-streaming only; sovereign concerns live in the runner, not here.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping

import requests

from shared.inference.errors import ErrorClass, InferenceError, classify
from shared.inference.retry import with_retry


@dataclass(frozen=True)
class Message:
    role: str   # system | user | assistant
    content: str


@dataclass(frozen=True)
class ChatRequest:
    messages: list[Message]
    temperature: float
    top_p: float
    max_tokens: int
    seed: int | None = None
    logprobs: bool = False
    top_logprobs: int | None = None
    stop: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class ChatResponse:
    content: str
    usage: Usage
    raw: Mapping[str, Any]   # full OpenAI response for storage


class InferenceClient:
    """Stateless OpenAI-compatible client. One instance per (endpoint, model)."""

    def __init__(self, endpoint: str, model: str, timeout_s: float) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def chat(self, req: ChatRequest) -> ChatResponse:
        body = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in req.messages],
            "temperature": req.temperature,
            "top_p": req.top_p,
            "max_tokens": req.max_tokens,
        }
        if req.seed is not None:
            body["seed"] = req.seed
        if req.logprobs:
            body["logprobs"] = True
            if req.top_logprobs is not None:
                body["top_logprobs"] = req.top_logprobs
        if req.stop:
            body["stop"] = req.stop

        url = f"{self.endpoint}/chat/completions"
        return with_retry(
            lambda: self._post_chat(url, body),
            is_retryable=lambda e: isinstance(e, InferenceError)
                                   and e.error_class is ErrorClass.RETRYABLE,
            is_rate_limit=lambda e: isinstance(e, InferenceError)
                                    and e.error_class is ErrorClass.RATE_LIMIT,
            retry_after_s=lambda e: (
                float(e.body["retry_after"])
                if isinstance(e, InferenceError) and isinstance(e.body, dict)
                and "retry_after" in e.body
                else None
            ),
            sleep=time.sleep,
        )

    def _post_chat(self, url: str, body: Mapping[str, Any]) -> ChatResponse:
        try:
            resp = requests.post(url, json=body, timeout=self.timeout_s)
        except requests.RequestException as e:
            raise InferenceError(str(e), ErrorClass.RETRYABLE, None, None) from e
        return self._parse_chat(resp)

    @staticmethod
    def _parse_chat(resp: "requests.Response") -> ChatResponse:
        try:
            body = resp.json()
        except ValueError as e:
            raise InferenceError("malformed json", ErrorClass.CATASTROPHIC,
                                 resp.status_code, None) from e
        if resp.status_code != 200:
            cls = classify(resp.status_code, body)
            raise InferenceError(
                f"http {resp.status_code}: {body.get('error', {}).get('message', '')}",
                cls, resp.status_code, body,
            )
        choice = body["choices"][0]["message"]["content"]
        u = body.get("usage", {}) or {}
        usage = Usage(
            prompt_tokens=int(u.get("prompt_tokens", 0)),
            completion_tokens=int(u.get("completion_tokens", 0)),
            total_tokens=int(u.get("total_tokens", 0)),
        )
        return ChatResponse(content=choice, usage=usage, raw=body)
