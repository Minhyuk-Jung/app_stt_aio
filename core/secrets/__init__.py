"""C19 minimal secret store (P2 bridge for C14)."""

from __future__ import annotations

LLM_API_KEY_SECRET = "llm.openai_compat.api_key"
STT_API_KEY_SECRET = "stt.cloud.api_key"

from core.secrets.masking import mask_secrets
from core.secrets.store import SecretStore, get_default_store, reset_default_store

__all__ = [
    "LLM_API_KEY_SECRET",
    "STT_API_KEY_SECRET",
    "SecretStore",
    "get_default_store",
    "mask_secrets",
    "reset_default_store",
]
