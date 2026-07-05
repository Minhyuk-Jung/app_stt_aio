"""Remote gateway → SessionManager integration (C15 §10)."""

from __future__ import annotations

import asyncio
import wave
from io import BytesIO
from unittest.mock import MagicMock, patch

import httpx
import pytest

pytest.importorskip("fastapi")

from app.config import Config
from app.session import SessionManager
from app.session.types import SessionArtifact as SessionSessionArtifact
from core.inject.types import InjectMethod, InjectResult
from core.pipeline import StageArtifact
from core.stt.types import STTResult
from core.store.models import SessionSource, SessionStatus
from remote.gateway.app import create_app
from remote.gateway.pairing import PairingManager


def _wav_bytes(*, duration_sec: float = 0.2) -> bytes:
    buf = BytesIO()
    frames = int(16000 * duration_sec)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


async def _upload_wav(app, pin: str) -> dict:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        pair = await client.post("/api/v1/pair", json={"pin": pin})
        assert pair.status_code == 200
        token = pair.json()["token"]
        upload = await client.post(
            "/api/v1/transcribe",
            files={"file": ("a.wav", _wav_bytes(), "audio/wav")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert upload.status_code == 200
        return upload.json()


def test_remote_upload_creates_session_and_artifact(tmp_path) -> None:
    config = Config.open(tmp_path / "remote_e2e.db", migrate_backup=False)
    config.bind_pipeline()
    capture = MagicMock()
    manager = SessionManager(config, capture)
    pairing = PairingManager(bootstrap_secret=False)
    pin = pairing.issue_pin()
    app = create_app(manager, pairing=pairing)
    captured: dict = {}

    def fake_stage1(_config, audio, session_id, **kwargs) -> tuple:
        captured["session_id"] = session_id
        captured["audio"] = audio
        return (
            STTResult(text="원격 녹음", language="ko", provider_id="mock-stt"),
            StageArtifact(
                session_id=session_id,
                stage=1,
                text="원격 녹음",
                language="ko",
                provider="mock-stt",
            ),
        )

    with patch("core.pipeline.pipeline.run_stage1", side_effect=fake_stage1):
        with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
            mock_inject.return_value = InjectResult(
                success=True,
                method_used=InjectMethod.UNICODE,
                chars_injected=4,
            )
            body = asyncio.run(_upload_wav(app, pin))
            session_id = body["session_id"]
            manager._wait_for_workers(timeout_sec=5.0)

    stored = config._store.sessions.get(session_id)
    assert stored is not None
    assert stored.source is SessionSource.REMOTE
    assert stored.status is SessionStatus.DONE
    artifacts = config._store.artifacts.get_by_session(session_id)
    assert len(artifacts) == 1
    assert artifacts[0].stage == 1
    assert artifacts[0].text == "원격 녹음"
    assert artifacts[0].provider == "mock-stt"
    assert captured["session_id"] == session_id
    assert captured["audio"].sample_rate == 16000
    manager.close()
    config.close()


def test_remote_webm_upload_with_mock_ffmpeg(tmp_path) -> None:
    config = Config.open(tmp_path / "remote_webm.db", migrate_backup=False)
    config.bind_pipeline()
    manager = SessionManager(config, MagicMock())
    pairing = PairingManager(bootstrap_secret=False)
    pin = pairing.issue_pin()
    app = create_app(manager, pairing=pairing)
    pcm = b"\x00\x01" * 800

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        out_path = cmd[-1]
        with open(out_path, "wb") as fh:
            fh.write(pcm)
        return type("R", (), {"returncode": 0})()

    with patch("app.session.session_manager.run_batch_pipeline") as mock_pipeline:
        mock_pipeline.return_value = (
            STTResult(text="webm", language="ko", provider_id="mock"),
            SessionSessionArtifact(
                session_id="x",
                stage=1,
                text="webm",
                language="ko",
                inject_result=InjectResult(
                    success=True,
                    method_used=InjectMethod.UNICODE,
                    chars_injected=2,
                ),
            ),
        )
        with patch("core.audio.webm_convert.shutil.which", return_value="ffmpeg"):
            with patch("core.audio.webm_convert.subprocess.run", side_effect=fake_run):
                transport = httpx.ASGITransport(app=app)
                session_ids: list[str] = []

                async def _run() -> None:
                    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                        token = (await client.post("/api/v1/pair", json={"pin": pin})).json()["token"]
                        res = await client.post(
                            "/api/v1/transcribe",
                            files={"file": ("r.webm", b"\x1a\x45\xdf\xa3data", "audio/webm")},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        assert res.status_code == 200
                        session_ids.append(res.json()["session_id"])

                asyncio.run(_run())

    manager._wait_for_workers(timeout_sec=2.0)
    assert session_ids
    manager.close()
    config.close()


async def _two_uploads(app, pin: str, manager: SessionManager, *, wait_between: bool) -> list[str]:
    """Remote uploads via the same gateway (sequential or concurrent)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        token = (await client.post("/api/v1/pair", json={"pin": pin})).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        async def _upload(name: str) -> str:
            res = await client.post(
                "/api/v1/transcribe",
                files={"file": (name, _wav_bytes(), "audio/wav")},
                headers=headers,
            )
            assert res.status_code == 200
            session_id = res.json()["session_id"]
            if wait_between:
                manager._wait_for_workers(timeout_sec=5.0)
            return session_id

        if wait_between:
            return [await _upload("a.wav"), await _upload("b.wav")]
        return list(await asyncio.gather(_upload("a.wav"), _upload("b.wav")))


def _run_remote_upload_scenario(tmp_path, *, wait_between: bool) -> None:
    config = Config.open(tmp_path / "remote_concurrent.db", migrate_backup=False)
    config.bind_pipeline()
    manager = SessionManager(config, MagicMock())
    pairing = PairingManager(bootstrap_secret=False)
    pin = pairing.issue_pin()
    app = create_app(manager, pairing=pairing)

    def fake_stage1(_config, audio, session_id, **kwargs) -> tuple:
        return (
            STTResult(text="동시", language="ko", provider_id="mock-stt"),
            StageArtifact(
                session_id=session_id,
                stage=1,
                text="동시",
                language="ko",
                provider="mock-stt",
            ),
        )

    with patch("core.pipeline.pipeline.run_stage1", side_effect=fake_stage1):
        with patch("core.pipeline.pipeline.inject_stage_text") as mock_inject:
            mock_inject.return_value = InjectResult(
                success=True,
                method_used=InjectMethod.UNICODE,
                chars_injected=2,
            )
            session_ids = asyncio.run(_two_uploads(app, pin, manager, wait_between=wait_between))
            manager._wait_for_workers(timeout_sec=5.0)

    assert len(set(session_ids)) == 2
    for session_id in session_ids:
        artifacts = config._store.artifacts.get_by_session(session_id)
        assert len(artifacts) == 1
    manager.close()
    config.close()


def test_sequential_remote_uploads(tmp_path) -> None:
    _run_remote_upload_scenario(tmp_path, wait_between=True)


def test_concurrent_remote_uploads(tmp_path) -> None:
    _run_remote_upload_scenario(tmp_path, wait_between=False)
