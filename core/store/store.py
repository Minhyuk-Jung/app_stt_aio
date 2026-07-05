"""Unified Store entry point for upper layers."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import sqlite3

from core.paths import AppPaths, ensure_app_dirs
from core.store.db import Database
from core.store.repos.artifact_repo import ArtifactRepo
from core.store.repos.dictionary_repo import DictionaryRepo
from core.store.repos.mode_repo import ModeRepo
from core.store.repos.session_repo import SessionRepo
from core.store.repos.setting_repo import SettingRepo


class Store:
    """Facade exposing Database and P1 repositories."""

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        migrate_backup: bool = True,
        readonly: bool = False,
    ) -> None:
        self.db = Database(db_path, migrate_backup=migrate_backup, readonly=readonly)
        self.sessions = SessionRepo(self.db)
        self.artifacts = ArtifactRepo(self.db)
        self.modes = ModeRepo(self.db)
        self.dictionaries = DictionaryRepo(self.db)
        self.settings = SettingRepo(self.db)
        self._readonly = readonly

    @classmethod
    def open_readonly(cls, db_path: Path | None = None) -> Store:
        """Open store in safe read-only mode after migration/integrity failures."""
        return cls(db_path, migrate_backup=False, readonly=True)

    @property
    def readonly(self) -> bool:
        return self._readonly or self.db.readonly

    @classmethod
    def from_paths(cls, paths: AppPaths, *, migrate_backup: bool = True) -> Store:
        ensure_app_dirs(paths)
        return cls(paths.db, migrate_backup=migrate_backup)

    @property
    def schema_version(self) -> int:
        return self.db.schema_version

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Expose a multi-repo transaction boundary (C6 contract)."""
        with self.db.transaction() as conn:
            yield conn

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
