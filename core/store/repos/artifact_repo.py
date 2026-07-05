"""Artifact repository (C6/C4)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from core.store.db import Database
from core.store.models import Artifact


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _row_to_artifact(row) -> Artifact:
    return Artifact(
        id=row["id"],
        session_id=row["session_id"],
        stage=int(row["stage"]),
        text=row["text"],
        provider=row["provider"],
        prompt_snapshot=row["prompt_snapshot"],
        created_at=_from_iso(row["created_at"]),
    )


class ArtifactRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(
        self,
        session_id: str,
        stage: int,
        text: str,
        *,
        provider: str | None = None,
        prompt_snapshot: str | None = None,
        artifact_id: str | None = None,
    ) -> Artifact:
        artifact = Artifact(
            id=artifact_id or str(uuid.uuid4()),
            session_id=session_id,
            stage=stage,
            text=text,
            provider=provider,
            prompt_snapshot=prompt_snapshot,
            created_at=_utc_now(),
        )
        with self._db.transaction():
            self._db.execute(
                """
                INSERT INTO artifacts (
                    id, session_id, stage, text, provider, prompt_snapshot, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.id,
                    artifact.session_id,
                    artifact.stage,
                    artifact.text,
                    artifact.provider,
                    artifact.prompt_snapshot,
                    _to_iso(artifact.created_at),
                ),
            )
        return artifact

    def get_by_session(self, session_id: str) -> list[Artifact]:
        rows = self._db.execute(
            """
            SELECT * FROM artifacts
            WHERE session_id = ?
            ORDER BY stage ASC, created_at ASC
            """,
            (session_id,),
        ).fetchall()
        return [_row_to_artifact(row) for row in rows]

    def latest_by_stage(self, session_id: str, stage: int) -> Artifact | None:
        row = self._db.execute(
            """
            SELECT * FROM artifacts
            WHERE session_id = ? AND stage = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session_id, stage),
        ).fetchone()
        return _row_to_artifact(row) if row else None

    def update_text(self, artifact_id: str, text: str) -> Artifact | None:
        with self._db.transaction():
            self._db.execute(
                "UPDATE artifacts SET text = ? WHERE id = ?",
                (text, artifact_id),
            )
        row = self._db.execute(
            "SELECT * FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        return _row_to_artifact(row) if row else None
