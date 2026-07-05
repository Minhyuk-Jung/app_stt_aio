"""Tests for C6 Store."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.store import Store
from core.store.db import Database
from core.store.errors import SecretKeyRejectedError
from core.store.migrations import v001_initial
from core.store.models import SessionSource, SessionStatus
from core.store.repos.session_repo import SessionRepo
from core.store.repos.setting_repo import SettingRepo


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db", migrate_backup=False)
    yield database
    database.close()


def test_migration_creates_schema(db: Database) -> None:
    assert db.schema_version == 6
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {
        "schema_meta",
        "sessions",
        "settings",
        "artifacts",
        "modes",
        "dictionaries",
    }.issubset(tables)

    indexes = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert "idx_sessions_status" in indexes
    assert "idx_sessions_source" in indexes


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "idempotent.db"
    with Database(db_path, migrate_backup=False) as first:
        assert first.schema_version == 6
    with Database(db_path, migrate_backup=False) as second:
        assert second.schema_version == 6


def test_migration_backup_on_upgrade(tmp_path: Path) -> None:
    db_path = tmp_path / "upgrade.db"
    conn = sqlite3.connect(str(db_path))
    conn.isolation_level = None
    v001_initial.up(conn)
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO schema_meta (id, version) VALUES (1, 1)"
    )
    conn.execute("COMMIT")
    conn.close()

    backup_path = db_path.with_suffix(".db.bak")
    with Database(db_path, migrate_backup=True) as db:
        assert db.schema_version == 6
    assert backup_path.exists()


def test_store_facade(tmp_path: Path) -> None:
    with Store(tmp_path / "facade.db", migrate_backup=False) as store:
        assert store.schema_version == 6
        session = store.sessions.create(source=SessionSource.BATCH)
        store.settings.set("stt.provider", "local")
        assert store.sessions.get(session.id) is not None
        assert store.settings.get("stt.provider") == "local"


def test_database_backup(tmp_path: Path) -> None:
    db_path = tmp_path / "backup.db"
    with Database(db_path, migrate_backup=False) as db:
        SessionRepo(db).create(source=SessionSource.BATCH)
        backup_path = db.backup_database()

    assert backup_path.exists()
    assert db_path.exists()


def test_session_crud(db: Database) -> None:
    repo = SessionRepo(db)
    session = repo.create(
        source=SessionSource.BATCH,
        mode_id="quick-dictation",
        status=SessionStatus.RECORDING,
    )
    assert session.id
    assert session.source == SessionSource.BATCH

    updated = repo.update_status(session.id, SessionStatus.PROCESSING)
    assert updated is not None
    assert updated.status == SessionStatus.PROCESSING

    repo.update_audio_path(session.id, r"C:\audio\test.wav")
    updated_mode = repo.update_mode_id(session.id, "meeting")
    assert updated_mode is not None
    assert updated_mode.mode_id == "meeting"

    fetched = repo.get(session.id)
    assert fetched is not None
    assert fetched.audio_path == r"C:\audio\test.wav"

    sessions = repo.list(limit=10)
    assert len(sessions) == 1

    assert repo.delete(session.id) is True
    assert repo.get(session.id) is None


def test_session_list_filter_and_paging(db: Database) -> None:
    repo = SessionRepo(db)
    repo.create(source=SessionSource.BATCH, status=SessionStatus.DONE)
    repo.create(source=SessionSource.REALTIME, status=SessionStatus.ERROR)
    repo.create(source=SessionSource.BATCH, status=SessionStatus.DONE)

    assert repo.count() == 3
    assert repo.count(status=SessionStatus.DONE) == 2
    assert repo.count(source=SessionSource.REALTIME) == 1

    done_batch = repo.list(
        status=SessionStatus.DONE,
        source=SessionSource.BATCH,
        limit=10,
    )
    assert len(done_batch) == 2

    page = repo.list(limit=1, offset=1)
    assert len(page) == 1


def test_session_list_mode_filter(db: Database) -> None:
    repo = SessionRepo(db)
    repo.create(source=SessionSource.BATCH, mode_id="quick-dictation", status=SessionStatus.DONE)
    repo.create(source=SessionSource.BATCH, mode_id="meeting", status=SessionStatus.DONE)

    assert repo.count(mode_id="quick-dictation") == 1
    listed = repo.list(mode_id="meeting")
    assert len(listed) == 1
    assert listed[0].mode_id == "meeting"


def test_session_search_by_artifact_text(db: Database) -> None:
    from core.store.repos.artifact_repo import ArtifactRepo

    repo = SessionRepo(db)
    artifacts = ArtifactRepo(db)
    session = repo.create(source=SessionSource.BATCH, status=SessionStatus.DONE)
    artifacts.add(session.id, 1, "회의록 요약 내용", provider="stt")
    other = repo.create(source=SessionSource.BATCH, status=SessionStatus.DONE)
    artifacts.add(other.id, 1, "다른 텍스트", provider="stt")

    matches = repo.search("회의록")
    assert len(matches) == 1
    assert matches[0].id == session.id
    assert repo.search_count("회의록") == 1


def test_setting_crud(db: Database) -> None:
    repo = SettingRepo(db)
    assert repo.get("stt.provider") is None

    repo.set("stt.provider", "faster_whisper_local")
    assert repo.get("stt.provider") == "faster_whisper_local"

    repo.set("stt.provider", "groq")
    assert repo.get("stt.provider") == "groq"

    all_settings = repo.get_all()
    assert all_settings["stt.provider"] == "groq"

    assert repo.delete("stt.provider") is True
    assert repo.get("stt.provider") is None


def test_setting_rejects_secret_like_keys(db: Database) -> None:
    repo = SettingRepo(db)
    with pytest.raises(SecretKeyRejectedError):
        repo.set("stt.api_key", "should-not-store")


def test_setting_get_all_excludes_secret_like_keys(db: Database) -> None:
    repo = SettingRepo(db)
    repo.set("stt.provider", "local")
    with pytest.raises(SecretKeyRejectedError):
        repo.set("llm.api_key", "secret")

    all_settings = repo.get_all()
    assert all_settings == {"stt.provider": "local"}


def test_transaction_rollback(db: Database) -> None:
    with pytest.raises(RuntimeError):
        with db.transaction():
            db.execute(
                """
                INSERT INTO sessions (id, created_at, source, mode_id, audio_path, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "rollback-test",
                    "2026-01-01T00:00:00+00:00",
                    "batch",
                    None,
                    None,
                    "recording",
                ),
            )
            raise RuntimeError("force rollback")

    count = db.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
    assert count == 0


def test_nested_repo_transaction_rollback(db: Database) -> None:
    session_repo = SessionRepo(db)
    setting_repo = SettingRepo(db)

    with pytest.raises(RuntimeError):
        with db.transaction():
            session_repo.create(source=SessionSource.BATCH)
            setting_repo.set("stt.provider", "local")
            raise RuntimeError("rollback all")

    assert session_repo.list() == []
    assert setting_repo.get_all() == {}


def test_store_transaction_facade(tmp_path: Path) -> None:
    with Store(tmp_path / "tx.db", migrate_backup=False) as store:
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.sessions.create(source=SessionSource.BATCH)
                store.settings.set("stt.provider", "local")
                raise RuntimeError("rollback")

        assert store.sessions.list() == []
        assert store.settings.get_all() == {}


def test_mode_repo_crud(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    from core.store.models import Mode

    with Store(tmp_path / "modes.db", migrate_backup=False) as store:
        now = datetime.now(timezone.utc)
        mode = Mode(
            id="custom",
            name="커스텀",
            target_stage=1,
            inject_stage=1,
            correction_prompt="",
            report_prompt="",
            stt_provider=None,
            llm_provider=None,
            is_default=False,
            is_builtin=False,
            enabled=True,
            updated_at=now,
        )
        created = store.modes.create(mode)
        assert created.id == "custom"

        fetched = store.modes.get("custom")
        assert fetched is not None
        assert fetched.name == "커스텀"

        updated = store.modes.update(
            Mode(
                id="custom",
                name="수정",
                target_stage=2,
                inject_stage=2,
                correction_prompt="p2",
                report_prompt="",
                stt_provider=None,
                llm_provider=None,
                is_default=False,
                is_builtin=False,
                enabled=True,
                updated_at=now,
            )
        )
        assert updated.target_stage == 2

        assert store.modes.delete("custom") is True
        assert store.modes.get("custom") is None


def test_artifact_repo_crud(tmp_path: Path) -> None:
    with Store(tmp_path / "artifacts.db", migrate_backup=False) as store:
        session = store.sessions.create(source=SessionSource.BATCH)
        first = store.artifacts.add(session.id, 1, "1차 텍스트", provider="stt")
        second = store.artifacts.add(session.id, 2, "2차 텍스트", provider="llm")

        by_session = store.artifacts.get_by_session(session.id)
        assert [item.stage for item in by_session] == [1, 2]
        assert store.artifacts.latest_by_stage(session.id, 1) == first

        updated = store.artifacts.update_text(first.id, "수정된 1차")
        assert updated is not None
        assert updated.text == "수정된 1차"
        assert second.text == "2차 텍스트"


def test_database_concurrent_status_updates(db: Database) -> None:
    """Worker + request threads must not corrupt nested savepoints (P5)."""
    import threading

    repo = SessionRepo(db)
    session = repo.create(source=SessionSource.REMOTE, mode_id="default", status=SessionStatus.PROCESSING)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for status in (SessionStatus.PROCESSING, SessionStatus.DONE):
                repo.update_status(session.id, status)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    repo.update_status(session.id, SessionStatus.PROCESSING)
    thread.join(timeout=5.0)
    assert not errors
    assert thread.is_alive() is False
    final = repo.get(session.id)
    assert final is not None
    assert final.status in {SessionStatus.PROCESSING, SessionStatus.DONE}
