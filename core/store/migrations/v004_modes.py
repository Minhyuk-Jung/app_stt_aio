"""Add modes table for C7 ModeManager."""

from __future__ import annotations

import sqlite3

_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS modes (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        target_stage INTEGER NOT NULL CHECK (target_stage BETWEEN 1 AND 3),
        inject_stage INTEGER NOT NULL CHECK (inject_stage BETWEEN 0 AND 3),
        correction_prompt TEXT NOT NULL DEFAULT '',
        report_prompt TEXT NOT NULL DEFAULT '',
        stt_provider TEXT,
        llm_provider TEXT,
        is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
        is_builtin INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0, 1)),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_modes_enabled
        ON modes(enabled, name)
    """,
]


def up(conn: sqlite3.Connection) -> None:
    for statement in _STATEMENTS:
        conn.execute(statement)
