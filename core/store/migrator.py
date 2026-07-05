"""Schema migration runner."""

from __future__ import annotations

import logging
import shutil
import sqlite3
from pathlib import Path
from typing import Callable

from core.store.errors import MigrationError
from core.store.migrations import (
    v001_initial,
    v002_session_indexes,
    v003_artifacts,
    v004_modes,
    v005_dictionaries,
    v006_dictionary_target_app,
)

logger = logging.getLogger(__name__)

MigrationFn = Callable[[sqlite3.Connection], None]

MIGRATIONS: list[tuple[int, MigrationFn]] = [
    (1, v001_initial.up),
    (2, v002_session_indexes.up),
    (3, v003_artifacts.up),
    (4, v004_modes.up),
    (5, v005_dictionaries.up),
    (6, v006_dictionary_target_app.up),
]


class Migrator:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        db_path: Path | None = None,
    ) -> None:
        self._conn = conn
        self._db_path = db_path

    def current_version(self) -> int:
        row = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
        ).fetchone()
        if row is None:
            return 0
        version_row = self._conn.execute(
            "SELECT version FROM schema_meta WHERE id = 1"
        ).fetchone()
        return int(version_row["version"]) if version_row else 0

    def migrate_to_latest(self, *, backup: bool = False) -> int:
        current = self.current_version()
        pending = [item for item in MIGRATIONS if item[0] > current]
        if not pending:
            return current

        backup_path: Path | None = None
        if backup:
            backup_path = self._backup_if_exists()

        for version, migrate_fn in pending:
            try:
                self._conn.execute("BEGIN")
                migrate_fn(self._conn)
                self._conn.execute(
                    """
                    INSERT INTO schema_meta (id, version)
                    VALUES (1, ?)
                    ON CONFLICT(id) DO UPDATE SET version = excluded.version
                    """,
                    (version,),
                )
                self._conn.execute("COMMIT")
                current = version
                logger.info("Applied database migration v%s", version)
            except Exception as exc:
                self._conn.execute("ROLLBACK")
                message = f"Failed to apply migration v{version}: {exc}"
                if backup_path is not None:
                    message += f" Restore backup from: {backup_path}"
                raise MigrationError(message, backup_path=backup_path) from exc
        return current

    def _backup_if_exists(self) -> Path | None:
        if self._db_path is None or not self._db_path.exists():
            return None
        backup_path = self._db_path.with_suffix(".db.bak")
        shutil.copy2(self._db_path, backup_path)
        logger.info("Database backup created at %s", backup_path)
        return backup_path
