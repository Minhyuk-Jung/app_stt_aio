"""Model resolution errors (shared by C2 STT and C18 ModelManager)."""

from __future__ import annotations


class ModelError(Exception):
    """Base error for model path/download operations."""


class ModelNotFoundError(ModelError):
    """Requested model is not installed or unknown."""


class ModelDownloadError(ModelError):
    """Model download or verification failed."""
