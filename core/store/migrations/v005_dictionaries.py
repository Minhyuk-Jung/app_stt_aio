"""Add dictionaries table for C17 TextProcessor."""

from __future__ import annotations

import sqlite3

_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS dictionaries (
        id TEXT PRIMARY KEY,
        term TEXT NOT NULL,
        replacement TEXT NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('vocab', 'snippet')),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_dictionaries_type_enabled
        ON dictionaries(type, enabled)
    """,
]


def up(conn: sqlite3.Connection) -> None:
    for statement in _STATEMENTS:
        conn.execute(statement)
