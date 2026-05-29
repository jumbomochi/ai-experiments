"""OpenAI-compatible inference client and error handling."""

from shared.inference.client import (
    ChatRequest,
    ChatResponse,
    InferenceClient,
    Message,
    Usage,
)
from shared.inference.errors import ErrorClass, InferenceError

__all__ = [
    "InferenceClient",
    "ChatRequest",
    "Message",
    "ChatResponse",
    "Usage",
    "ErrorClass",
    "InferenceError",
]
