"""Settings repository (non-sensitive values only)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from core.store.db import Database
from core.store.errors import SecretKeyRejectedError
from core.store.models import Setting

_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|secret|password|token|credential)",
    re.IGNORECASE,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _row_to_setting(row) -> Setting:
    return Setting(
        key=row["key"],
        value=row["value"],
        updated_at=_from_iso(row["updated_at"]),
    )


class SettingRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    @staticmethod
    def _validate_key(key: str) -> None:
        if _SECRET_KEY_PATTERN.search(key):
            raise SecretKeyRejectedError(
                f"Setting key '{key}' looks sensitive. Use C19 Secrets instead."
            )

    def get(self, key: str) -> str | None:
        row = self._db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set(self, key: str, value: str) -> Setting:
        self._validate_key(key)
        now = _utc_now()
        with self._db.transaction():
            self._db.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, _to_iso(now)),
            )
        return Setting(key=key, value=value, updated_at=now)

    def delete(self, key: str) -> bool:
        with self._db.transaction():
            cursor = self._db.execute(
                "DELETE FROM settings WHERE key = ?", (key,)
            )
        return cursor.rowcount > 0

    def get_all(self) -> dict[str, str]:
        rows = self._db.execute("SELECT key, value FROM settings").fetchall()
        return {
            row["key"]: row["value"]
            for row in rows
            if not _SECRET_KEY_PATTERN.search(row["key"])
        }
