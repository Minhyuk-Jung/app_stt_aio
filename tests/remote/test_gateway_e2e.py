"""Remote gateway E2E (C15 §10)."""

from __future__ import annotations

import asyncio
import wave
from io import BytesIO
from unittest.mock import MagicMock

import httpx
import pytest

pytest.importorskip("fastapi")

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


async def _pair_and_transcribe_wav(app, sessions: MagicMock, pin: str) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        health = await client.get("/health")
        assert health.status_code == 200

        bad = await client.post("/api/v1/pair", json={"pin": "0000"})
        assert bad.status_code == 403

        ok = await client.post("/api/v1/pair", json={"pin": pin})
        assert ok.status_code == 200
        token = ok.json()["token"]

        unauthorized = await client.post(
            "/api/v1/transcribe",
            files={"file": ("a.wav", _wav_bytes(), "audio/wav")},
        )
        assert unauthorized.status_code == 401

        upload = await client.post(
            "/api/v1/transcribe",
            files={"file": ("a.wav", _wav_bytes(), "audio/wav")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert upload.status_code == 200
        body = upload.json()
        assert body["session_id"] == "session-abc"
        assert body["status"] == "processing"
        sessions.submit_remote.assert_called_once()


def test_pair_and_transcribe_wav() -> None:
    sessions = MagicMock()
    sessions.submit_remote.return_value = "session-abc"
    pairing = PairingManager(bootstrap_secret=False)
    pin = pairing.issue_pin()
    app = create_app(sessions, pairing=pairing)
    asyncio.run(_pair_and_transcribe_wav(app, sessions, pin))


async def _pwa_index_available(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/pwa/")
        assert response.status_code == 200
        assert "HTTPS" in response.text or "원격 녹음" in response.text


def test_pwa_index_available() -> None:
    sessions = MagicMock()
    app = create_app(sessions, pairing=PairingManager(bootstrap_secret=False))
    asyncio.run(_pwa_index_available(app))
