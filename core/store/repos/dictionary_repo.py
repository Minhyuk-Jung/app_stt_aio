"""Dictionary repository for C17 TextProcessor."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from core.store.db import Database
from core.store.models import DictionaryEntry, DictionaryType


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _row_to_entry(row) -> DictionaryEntry:
    keys = row.keys() if hasattr(row, "keys") else ()
    target_app = row["target_app"] if "target_app" in keys else None
    return DictionaryEntry(
        id=row["id"],
        term=row["term"],
        replacement=row["replacement"],
        type=DictionaryType(row["type"]),
        enabled=bool(row["enabled"]),
        updated_at=_from_iso(row["updated_at"]),
        target_app=target_app,
    )


_SELECT_COLUMNS = "id, term, replacement, type, enabled, updated_at, target_app"


class DictionaryRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def list_enabled(self, entry_type: DictionaryType | None = None) -> list[DictionaryEntry]:
        if entry_type is None:
            rows = self._db.execute(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM dictionaries
                WHERE enabled = 1
                ORDER BY LENGTH(term) DESC, term ASC
                """
            ).fetchall()
        else:
            rows = self._db.execute(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM dictionaries
                WHERE enabled = 1 AND type = ?
                ORDER BY LENGTH(term) DESC, term ASC
                """,
                (entry_type.value,),
            ).fetchall()
        return [_row_to_entry(row) for row in rows]

    def list_all(self, entry_type: DictionaryType | None = None) -> list[DictionaryEntry]:
        if entry_type is None:
            rows = self._db.execute(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM dictionaries
                ORDER BY LENGTH(term) DESC, term ASC
                """
            ).fetchall()
        else:
            rows = self._db.execute(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM dictionaries
                WHERE type = ?
                ORDER BY LENGTH(term) DESC, term ASC
                """,
                (entry_type.value,),
            ).fetchall()
        return [_row_to_entry(row) for row in rows]

    def get(self, entry_id: str) -> DictionaryEntry | None:
        row = self._db.execute(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM dictionaries
            WHERE id = ?
            """,
            (entry_id,),
        ).fetchone()
        return _row_to_entry(row) if row else None

    def create(
        self,
        *,
        term: str,
        replacement: str,
        entry_type: DictionaryType,
        enabled: bool = True,
        entry_id: str | None = None,
        target_app: str | None = None,
    ) -> DictionaryEntry:
        entry = DictionaryEntry(
            id=entry_id or str(uuid4()),
            term=term,
            replacement=replacement,
            type=entry_type,
            enabled=enabled,
            updated_at=_utc_now(),
            target_app=target_app,
        )
        self._db.execute(
            """
            INSERT INTO dictionaries
                (id, term, replacement, type, enabled, updated_at, target_app)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.term,
                entry.replacement,
                entry.type.value,
                int(entry.enabled),
                _to_iso(entry.updated_at),
                entry.target_app,
            ),
        )
        return entry

    def update(self, entry: DictionaryEntry) -> DictionaryEntry:
        entry = DictionaryEntry(
            id=entry.id,
            term=entry.term,
            replacement=entry.replacement,
            type=entry.type,
            enabled=entry.enabled,
            updated_at=_utc_now(),
            target_app=entry.target_app,
        )
        self._db.execute(
            """
            UPDATE dictionaries
            SET term = ?, replacement = ?, type = ?, enabled = ?,
                updated_at = ?, target_app = ?
            WHERE id = ?
            """,
            (
                entry.term,
                entry.replacement,
                entry.type.value,
                int(entry.enabled),
                _to_iso(entry.updated_at),
                entry.target_app,
                entry.id,
            ),
        )
        return entry

    def delete(self, entry_id: str) -> bool:
        cursor = self._db.execute(
            "DELETE FROM dictionaries WHERE id = ?",
            (entry_id,),
        )
        return cursor.rowcount > 0
