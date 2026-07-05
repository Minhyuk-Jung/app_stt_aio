"""Store layer exceptions."""

from __future__ import annotations

from pathlib import Path


class StoreError(Exception):
    """Base error for C6 Store."""


class DatabaseIntegrityError(StoreError):
    """SQLite integrity check failed."""


class MigrationError(StoreError):
    """Schema migration failed."""

    def __init__(self, message: str, *, backup_path: Path | None = None) -> None:
        super().__init__(message)
        self.backup_path = backup_path


class SecretKeyRejectedError(StoreError):
    """Attempted to store a sensitive value in settings table."""


class ReadOnlyStoreError(StoreError):
    """Write attempted on a read-only / safe-mode store."""
