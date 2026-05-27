"""OpenAI-compatible inference client and error handling."""

from shared.inference.client import InferenceClient
from shared.inference.errors import ErrorClass, InferenceError

__all__ = ["InferenceClient", "ErrorClass", "InferenceError"]
