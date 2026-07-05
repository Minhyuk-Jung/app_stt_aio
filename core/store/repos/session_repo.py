"""Session repository."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from core.store.db import Database
from core.store.models import Session, SessionSource, SessionStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _row_to_session(row) -> Session:
    return Session(
        id=row["id"],
        created_at=_from_iso(row["created_at"]),
        source=SessionSource(row["source"]),
        mode_id=row["mode_id"],
        audio_path=row["audio_path"],
        status=SessionStatus(row["status"]),
    )


class SessionRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create(
        self,
        source: SessionSource,
        mode_id: str | None = None,
        audio_path: str | None = None,
        status: SessionStatus = SessionStatus.RECORDING,
        session_id: str | None = None,
    ) -> Session:
        session = Session(
            id=session_id or str(uuid.uuid4()),
            created_at=_utc_now(),
            source=source,
            mode_id=mode_id,
            audio_path=audio_path,
            status=status,
        )
        with self._db.transaction():
            self._db.execute(
                """
                INSERT INTO sessions (id, created_at, source, mode_id, audio_path, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    _to_iso(session.created_at),
                    session.source.value,
                    session.mode_id,
                    session.audio_path,
                    session.status.value,
                ),
            )
        return session

    def get(self, session_id: str) -> Session | None:
        row = self._db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return _row_to_session(row) if row else None

    def update_status(self, session_id: str, status: SessionStatus) -> Session | None:
        with self._db.transaction():
            self._db.execute(
                "UPDATE sessions SET status = ? WHERE id = ?",
                (status.value, session_id),
            )
        return self.get(session_id)

    def update_audio_path(self, session_id: str, audio_path: str | None) -> Session | None:
        with self._db.transaction():
            self._db.execute(
                "UPDATE sessions SET audio_path = ? WHERE id = ?",
                (audio_path, session_id),
            )
        return self.get(session_id)

    def update_mode_id(self, session_id: str, mode_id: str | None) -> Session | None:
        with self._db.transaction():
            self._db.execute(
                "UPDATE sessions SET mode_id = ? WHERE id = ?",
                (mode_id, session_id),
            )
        return self.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._db.transaction():
            cursor = self._db.execute(
                "DELETE FROM sessions WHERE id = ?", (session_id,)
            )
        return cursor.rowcount > 0

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: SessionStatus | None = None,
        source: SessionSource | None = None,
        mode_id: str | None = None,
    ) -> list[Session]:
        where, params = self._filter_clause(
            status=status,
            source=source,
            mode_id=mode_id,
        )
        params.extend([limit, offset])

        rows = self._db.execute(
            f"""
            SELECT * FROM sessions
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        ).fetchall()
        return [_row_to_session(row) for row in rows]

    def count(
        self,
        *,
        status: SessionStatus | None = None,
        source: SessionSource | None = None,
        mode_id: str | None = None,
    ) -> int:
        where, params = self._filter_clause(
            status=status,
            source=source,
            mode_id=mode_id,
        )
        row = self._db.execute(
            f"SELECT COUNT(*) AS c FROM sessions {where}",
            tuple(params),
        ).fetchone()
        return int(row["c"])

    def search(
        self,
        query: str,
        *,
        limit: int = 50,
        offset: int = 0,
        status: SessionStatus | None = None,
        mode_id: str | None = None,
    ) -> list[Session]:
        """Match session id, mode_id, or stage-1 artifact text."""
        pattern = f"%{query.strip()}%"
        where, params = self._filter_clause(
            status=status,
            mode_id=mode_id,
            table_alias="s",
        )
        search_clause = (
            "(s.id LIKE ? OR IFNULL(s.mode_id, '') LIKE ? OR IFNULL(a.text, '') LIKE ?)"
        )
        if where:
            where = f"{where} AND {search_clause}"
        else:
            where = f"WHERE {search_clause}"
        params = [*params, pattern, pattern, pattern, limit, offset]

        rows = self._db.execute(
            f"""
            SELECT DISTINCT s.* FROM sessions s
            LEFT JOIN artifacts a ON a.session_id = s.id AND a.stage = 1
            {where}
            ORDER BY s.created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        ).fetchall()
        return [_row_to_session(row) for row in rows]

    def search_count(
        self,
        query: str,
        *,
        status: SessionStatus | None = None,
        mode_id: str | None = None,
    ) -> int:
        pattern = f"%{query.strip()}%"
        where, params = self._filter_clause(
            status=status,
            mode_id=mode_id,
            table_alias="s",
        )
        search_clause = (
            "(s.id LIKE ? OR IFNULL(s.mode_id, '') LIKE ? OR IFNULL(a.text, '') LIKE ?)"
        )
        if where:
            where = f"{where} AND {search_clause}"
        else:
            where = f"WHERE {search_clause}"
        params = [*params, pattern, pattern, pattern]

        row = self._db.execute(
            f"""
            SELECT COUNT(DISTINCT s.id) AS c FROM sessions s
            LEFT JOIN artifacts a ON a.session_id = s.id AND a.stage = 1
            {where}
            """,
            tuple(params),
        ).fetchone()
        return int(row["c"])

    @staticmethod
    def _filter_clause(
        *,
        status: SessionStatus | None = None,
        source: SessionSource | None = None,
        mode_id: str | None = None,
        table_alias: str | None = None,
    ) -> tuple[str, list[object]]:
        prefix = f"{table_alias}." if table_alias else ""
        clauses: list[str] = []
        params: list[object] = []

        if status is not None:
            clauses.append(f"{prefix}status = ?")
            params.append(status.value)
        if source is not None:
            clauses.append(f"{prefix}source = ?")
            params.append(source.value)
        if mode_id is not None:
            clauses.append(f"{prefix}mode_id = ?")
            params.append(mode_id)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, params
