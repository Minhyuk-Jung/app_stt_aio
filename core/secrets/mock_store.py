"""In-memory secret store for tests and non-Windows dev."""

from __future__ import annotations


class MemorySecretStore:
    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def set_secret(self, name: str, value: str) -> None:
        if not value.strip():
            raise ValueError("secret value cannot be empty")
        self._secrets[name] = value.strip()

    def get_secret(self, name: str) -> str | None:
        return self._secrets.get(name)

    def delete_secret(self, name: str) -> bool:
        return self._secrets.pop(name, None) is not None

    def has_secret(self, name: str) -> bool:
        return name in self._secrets

    def clear(self) -> None:
        self._secrets.clear()
