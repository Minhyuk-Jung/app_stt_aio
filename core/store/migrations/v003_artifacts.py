"""Artifacts table for pipeline stage outputs (P1/C4)."""

from __future__ import annotations

import sqlite3

_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS artifacts (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        stage INTEGER NOT NULL,
        text TEXT NOT NULL,
        provider TEXT,
        prompt_snapshot TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_artifacts_session_stage
        ON artifacts(session_id, stage)
    """,
]


def up(conn: sqlite3.Connection) -> None:
    for statement in _STATEMENTS:
        conn.execute(statement)
