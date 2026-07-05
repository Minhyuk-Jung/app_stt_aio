"""Secret store facade (C19/C14)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol

from core.secrets.mock_store import MemorySecretStore

_default_store: "SecretStore | None" = None


class SecretStore(Protocol):
    def set_secret(self, name: str, value: str) -> None: ...
    def get_secret(self, name: str) -> str | None: ...
    def delete_secret(self, name: str) -> bool: ...
    def has_secret(self, name: str) -> bool: ...


def get_default_store(*, path: Path | None = None, backend: str | None = None) -> SecretStore:
    global _default_store
    if _default_store is not None and path is None and backend is None:
        return _default_store

    import os

    selected = (backend or os.environ.get("STT_AIO_SECRET_BACKEND", "dpapi")).lower()
    if selected == "keyring":
        from core.secrets.backend_keyring import KeyringSecretStore

        store: SecretStore = KeyringSecretStore()
    elif sys.platform == "win32":
        from core.secrets.backend_win import DpapiFileSecretStore

        if path is None:
            from core.paths import get_app_paths

            path = get_app_paths().root / "secrets.dpapi"
        store = DpapiFileSecretStore(path)
    else:
        store = MemorySecretStore()
    if path is None or _default_store is None:
        _default_store = store
    return store


def reset_default_store(store: SecretStore | None = None) -> None:
    """Test helper to replace the process-wide secret store."""
    global _default_store
    _default_store = store
