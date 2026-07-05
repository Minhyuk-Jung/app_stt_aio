"""Additional indexes for session queries (P1 performance)."""

from __future__ import annotations

import sqlite3


def up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sessions_status
            ON sessions(status)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sessions_source
            ON sessions(source)
        """
    )
