"""Add optional target_app column for C17 app-specific rules."""

from __future__ import annotations

import sqlite3


def up(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(dictionaries)").fetchall()
    }
    if "target_app" not in columns:
        conn.execute(
            "ALTER TABLE dictionaries ADD COLUMN target_app TEXT DEFAULT NULL"
        )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_dictionaries_target_app
            ON dictionaries(target_app)
        """
    )
