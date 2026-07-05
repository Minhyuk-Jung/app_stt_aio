"""Initial schema: sessions + settings (P1 minimum)."""

from __future__ import annotations

import sqlite3

_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        version INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        source TEXT NOT NULL CHECK (source IN ('batch', 'realtime', 'remote')),
        mode_id TEXT,
        audio_path TEXT,
        status TEXT NOT NULL CHECK (
            status IN ('recording', 'processing', 'done', 'error', 'canceled')
        )
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_sessions_created_at
        ON sessions(created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
]


def up(conn: sqlite3.Connection) -> None:
    for statement in _STATEMENTS:
        conn.execute(statement)
