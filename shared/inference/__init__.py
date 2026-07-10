from __future__ import annotations

"""OpenAI-compatible inference client, error handling, and privacy guardrail."""

from shared.inference.client import (
    ChatRequest,
    ChatResponse,
    InferenceClient,
    Message,
    Usage,
)
from shared.inference.errors import ErrorClass, InferenceError
from shared.inference.guardrails import enforce_privacy_guardrail

__all__ = [
    "InferenceClient",
    "ChatRequest",
    "Message",
    "ChatResponse",
    "Usage",
    "ErrorClass",
    "InferenceError",
    "enforce_privacy_guardrail",
]
