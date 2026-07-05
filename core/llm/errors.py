"""LLM provider error types."""

from __future__ import annotations

__all__ = [
    "AuthenticationError",
    "CompletionError",
    "ContextExceededError",
    "LLMError",
    "ModelNotFoundError",
    "NetworkError",
    "ProviderNotFoundError",
]


class LLMError(Exception):
    """Base error for LLM operations."""


class ProviderNotFoundError(LLMError):
    """Unknown or unsupported provider id."""


class ModelNotFoundError(LLMError):
    """Requested model is not available."""


class AuthenticationError(LLMError):
    """Cloud provider rejected credentials (no retry)."""


class NetworkError(LLMError):
    """Network or timeout error talking to a provider."""


class ContextExceededError(LLMError):
    """Input exceeds provider context window."""


class CompletionError(LLMError):
    """Completion failed at runtime."""
