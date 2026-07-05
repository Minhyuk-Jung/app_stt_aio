"""Tests for C19 minimal secret store."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.secrets import LLM_API_KEY_SECRET, get_default_store, reset_default_store
from core.secrets.mock_store import MemorySecretStore


@pytest.fixture(autouse=True)
def memory_store():
    store = MemorySecretStore()
    reset_default_store(store)
    yield store
    reset_default_store(None)


def test_secret_store_roundtrip(memory_store: MemorySecretStore) -> None:
    memory_store.set_secret("test.key", "secret-value")
    assert memory_store.get_secret("test.key") == "secret-value"
    assert memory_store.has_secret("test.key") is True
    assert memory_store.delete_secret("test.key") is True
    assert memory_store.get_secret("test.key") is None


def test_get_default_store_uses_injected_memory_store(memory_store: MemorySecretStore) -> None:
    memory_store.set_secret(LLM_API_KEY_SECRET, "abc12345")
    assert get_default_store().get_secret(LLM_API_KEY_SECRET) == "abc12345"
