"""Windows Credential Manager backend via keyring (C19 optional)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SERVICE_NAME = "stt-aio"


class KeyringSecretStore:
    """Persist secrets in OS credential store when keyring is available."""

    def __init__(self, service_name: str = _SERVICE_NAME) -> None:
        self._service = service_name
        try:
            import keyring  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "keyring is not installed; pip install keyring to use Credential Manager"
            ) from exc
        self._keyring = keyring

    def set_secret(self, name: str, value: str) -> None:
        if not value.strip():
            raise ValueError("secret value cannot be empty")
        self._keyring.set_password(self._service, name, value.strip())

    def get_secret(self, name: str) -> str | None:
        return self._keyring.get_password(self._service, name)

    def delete_secret(self, name: str) -> bool:
        try:
            self._keyring.delete_password(self._service, name)
            return True
        except self._keyring.errors.PasswordDeleteError:
            return False

    def has_secret(self, name: str) -> bool:
        return self.get_secret(name) is not None


def keyring_available() -> bool:
    try:
        import keyring  # noqa: F401
    except ImportError:
        return False
    return True
