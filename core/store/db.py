"""Database connection and transaction management."""

from __future__ import annotations

import logging
import shutil
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from core.paths import AppPaths, ensure_app_dirs
from core.store.errors import DatabaseIntegrityError, MigrationError, ReadOnlyStoreError
from core.store.migrator import Migrator

logger = logging.getLogger(__name__)

_BUSY_TIMEOUT_MS = 5000
_BUSY_RETRY_ATTEMPTS = 3
_BUSY_RETRY_DELAY_SEC = 0.05


class Database:
    def __init__(
        self,
        db_path: Path | None = None,
        *,
        migrate_backup: bool = True,
        readonly: bool = False,
    ) -> None:
        if db_path is None:
            paths = ensure_app_dirs()
            db_path = paths.db
        else:
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db_path = db_path
        self._readonly = readonly
        self._tx_depth = 0
        self._conn_lock = threading.RLock()
        if readonly:
            uri = f"file:{db_path.as_posix()}?mode=ro"
            self._conn = sqlite3.connect(
                uri,
                uri=True,
                timeout=_BUSY_TIMEOUT_MS / 1000,
                check_same_thread=False,
            )
        else:
            self._conn = sqlite3.connect(
                str(db_path),
                timeout=_BUSY_TIMEOUT_MS / 1000,
                check_same_thread=False,
            )
        self._conn.isolation_level = None
        self._conn.row_factory = sqlite3.Row
        self._configure_pragmas()
        if not readonly:
            self._verify_integrity()
            self._migrator = Migrator(self._conn, db_path=self._db_path)
            try:
                self._migrator.migrate_to_latest(backup=migrate_backup)
            except MigrationError:
                raise
            except Exception as exc:
                raise MigrationError(f"Database migration failed: {exc}") from exc
        else:
            self._migrator = Migrator(self._conn, db_path=self._db_path)

    @property
    def readonly(self) -> bool:
        return self._readonly

    def _guard_write(self) -> None:
        if self._readonly:
            raise ReadOnlyStoreError(
                "Database is open in read-only safe mode; writes are disabled."
            )

    @property
    def path(self) -> Path:
        return self._db_path

    @property
    def schema_version(self) -> int:
        return self._migrator.current_version()

    @property
    def migrator(self) -> Migrator:
        return self._migrator

    @classmethod
    def from_paths(cls, paths: AppPaths, *, migrate_backup: bool = True) -> Database:
        ensure_app_dirs(paths)
        return cls(paths.db, migrate_backup=migrate_backup)

    def _configure_pragmas(self) -> None:
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")

    def _verify_integrity(self) -> None:
        row = self._conn.execute("PRAGMA integrity_check").fetchone()
        result = row[0] if row else "failed"
        if result != "ok":
            raise DatabaseIntegrityError(
                f"Database integrity check failed: {result}. "
                f"Consider restoring from backup: {self._db_path.with_suffix('.db.bak')}"
            )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._conn_lock:
            self._guard_write()
            self._tx_depth += 1
            savepoint = f"sp_{self._tx_depth}"
            is_outer = self._tx_depth == 1
            if is_outer:
                self._conn.execute("BEGIN")
            else:
                self._conn.execute(f"SAVEPOINT {savepoint}")
            try:
                yield self._conn
                if is_outer:
                    self._conn.execute("COMMIT")
                else:
                    self._conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception:
                if is_outer:
                    self._conn.execute("ROLLBACK")
                else:
                    self._conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self._conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            finally:
                self._tx_depth -= 1

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        if self._readonly and not sql.lstrip().upper().startswith("SELECT"):
            self._guard_write()
        with self._conn_lock:
            return self._execute_with_retry(lambda: self._conn.execute(sql, params))

    def executemany(self, sql: str, params_seq: list[tuple]) -> sqlite3.Cursor:
        if self._readonly:
            self._guard_write()
        with self._conn_lock:
            return self._execute_with_retry(
                lambda: self._conn.executemany(sql, params_seq)
            )

    def _execute_with_retry(self, operation):
        last_error: sqlite3.OperationalError | None = None
        for attempt in range(_BUSY_RETRY_ATTEMPTS):
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                last_error = exc
                if attempt < _BUSY_RETRY_ATTEMPTS - 1:
                    time.sleep(_BUSY_RETRY_DELAY_SEC * (attempt + 1))
        if last_error is not None:
            logger.warning(
                "Database busy after %s retries at %s",
                _BUSY_RETRY_ATTEMPTS,
                self._db_path,
            )
            raise last_error
        raise RuntimeError("execute retry failed without error")

    def backup_database(self, dest: Path | None = None) -> Path:
        dest = dest or self._db_path.with_suffix(".db.bak")
        if self._db_path.exists():
            shutil.copy2(self._db_path, dest)
        return dest

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
