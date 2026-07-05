"""Mode repository (C6/C7)."""

from __future__ import annotations

from datetime import datetime, timezone

from core.store.db import Database
from core.store.models import Mode


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _row_to_mode(row) -> Mode:
    return Mode(
        id=row["id"],
        name=row["name"],
        target_stage=int(row["target_stage"]),
        inject_stage=int(row["inject_stage"]),
        correction_prompt=row["correction_prompt"],
        report_prompt=row["report_prompt"],
        stt_provider=row["stt_provider"],
        llm_provider=row["llm_provider"],
        is_default=bool(row["is_default"]),
        is_builtin=bool(row["is_builtin"]),
        enabled=bool(row["enabled"]),
        updated_at=_from_iso(row["updated_at"]),
    )


class ModeRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def count(self) -> int:
        row = self._db.execute("SELECT COUNT(*) AS c FROM modes").fetchone()
        return int(row["c"])

    def create(self, mode: Mode) -> Mode:
        with self._db.transaction():
            if mode.is_default:
                self._db.execute("UPDATE modes SET is_default = 0")
            self._db.execute(
                """
                INSERT INTO modes (
                    id, name, target_stage, inject_stage,
                    correction_prompt, report_prompt,
                    stt_provider, llm_provider,
                    is_default, is_builtin, enabled, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mode.id,
                    mode.name,
                    mode.target_stage,
                    mode.inject_stage,
                    mode.correction_prompt,
                    mode.report_prompt,
                    mode.stt_provider,
                    mode.llm_provider,
                    int(mode.is_default),
                    int(mode.is_builtin),
                    int(mode.enabled),
                    _to_iso(mode.updated_at),
                ),
            )
        return self.get(mode.id) or mode

    def get(self, mode_id: str) -> Mode | None:
        row = self._db.execute(
            "SELECT * FROM modes WHERE id = ?", (mode_id,)
        ).fetchone()
        return _row_to_mode(row) if row else None

    def get_default(self) -> Mode | None:
        row = self._db.execute(
            "SELECT * FROM modes WHERE is_default = 1 LIMIT 1"
        ).fetchone()
        if row is not None:
            return _row_to_mode(row)
        row = self._db.execute(
            "SELECT * FROM modes WHERE enabled = 1 ORDER BY name LIMIT 1"
        ).fetchone()
        return _row_to_mode(row) if row else None

    def update(self, mode: Mode) -> Mode:
        with self._db.transaction():
            if mode.is_default:
                self._db.execute("UPDATE modes SET is_default = 0")
            self._db.execute(
                """
                UPDATE modes SET
                    name = ?,
                    target_stage = ?,
                    inject_stage = ?,
                    correction_prompt = ?,
                    report_prompt = ?,
                    stt_provider = ?,
                    llm_provider = ?,
                    is_default = ?,
                    enabled = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    mode.name,
                    mode.target_stage,
                    mode.inject_stage,
                    mode.correction_prompt,
                    mode.report_prompt,
                    mode.stt_provider,
                    mode.llm_provider,
                    int(mode.is_default),
                    int(mode.enabled),
                    _to_iso(mode.updated_at),
                    mode.id,
                ),
            )
        updated = self.get(mode.id)
        if updated is None:
            raise KeyError(mode.id)
        return updated

    def delete(self, mode_id: str) -> bool:
        with self._db.transaction():
            cursor = self._db.execute(
                "DELETE FROM modes WHERE id = ?", (mode_id,)
            )
        return cursor.rowcount > 0

    def list(
        self,
        *,
        enabled_only: bool = False,
    ) -> list[Mode]:
        if enabled_only:
            rows = self._db.execute(
                "SELECT * FROM modes WHERE enabled = 1 ORDER BY name"
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM modes ORDER BY name"
            ).fetchall()
        return [_row_to_mode(row) for row in rows]
