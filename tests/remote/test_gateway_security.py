"""C15 security policy tests — upload limits and auth (P4 §6.4)."""

from __future__ import annotations

import asyncio
import time
import wave
from io import BytesIO
from unittest.mock import MagicMock

import httpx
import pytest

pytest.importorskip("fastapi")

from remote.gateway.app import create_app
from remote.gateway.pairing import PairingManager


def _wav_bytes(*, duration_sec: float = 0.05) -> bytes:
    buf = BytesIO()
    frames = int(16000 * duration_sec)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


async def _pair_token(app, pin: str) -> str:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/pair", json={"pin": pin})
        assert response.status_code == 200
        return response.json()["token"]


def test_transcribe_rejects_oversized_upload() -> None:
    sessions = MagicMock()
    pairing = PairingManager(bootstrap_secret=False)
    pin = pairing.issue_pin()
    app = create_app(sessions, pairing=pairing)
    token = asyncio.run(_pair_token(app, pin))
    oversized = b"\x00" * (32 * 1024 * 1024 + 1)

    async def _upload() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/transcribe",
                files={"file": ("big.wav", oversized, "audio/wav")},
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.status_code

    assert asyncio.run(_upload()) == 413
    sessions.submit_remote.assert_not_called()


def test_transcribe_rejects_empty_file() -> None:
    sessions = MagicMock()
    pairing = PairingManager(bootstrap_secret=False)
    pin = pairing.issue_pin()
    app = create_app(sessions, pairing=pairing)
    token = asyncio.run(_pair_token(app, pin))

    async def _upload() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/transcribe",
                files={"file": ("empty.wav", b"", "audio/wav")},
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.status_code

    assert asyncio.run(_upload()) == 400
    sessions.submit_remote.assert_not_called()


def test_transcribe_rejects_expired_token() -> None:
    sessions = MagicMock()
    pairing = PairingManager(pin_ttl_sec=60, token_ttl_sec=1, bootstrap_secret=False)
    pin = pairing.issue_pin()
    app = create_app(sessions, pairing=pairing)
    token = asyncio.run(_pair_token(app, pin))
    time.sleep(1.1)

    async def _upload() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/transcribe",
                files={"file": ("a.wav", _wav_bytes(), "audio/wav")},
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.status_code

    assert asyncio.run(_upload()) == 401
    sessions.submit_remote.assert_not_called()


def test_pair_lockout_returns_429() -> None:
    sessions = MagicMock()
    pairing = PairingManager(
        bootstrap_secret=False,
        max_failed_attempts=2,
        lockout_sec=60,
    )
    pairing.issue_pin()
    app = create_app(sessions, pairing=pairing)

    async def _attempt() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post("/api/v1/pair", json={"pin": "0000"})
            second = await client.post("/api/v1/pair", json={"pin": "0000"})
            return second.status_code

    assert asyncio.run(_attempt()) == 429


def test_transcribe_rejects_long_recording(monkeypatch) -> None:
    from core.audio.format import AudioBuffer

    sessions = MagicMock()
    sessions.submit_remote.return_value = "sid"
    pairing = PairingManager(bootstrap_secret=False)
    pin = pairing.issue_pin()
    app = create_app(sessions, pairing=pairing)
    token = asyncio.run(_pair_token(app, pin))
    monkeypatch.setattr("remote.gateway.app.MAX_REMOTE_DURATION_MS", 50)

    def _long_buffer(data: bytes, *, content_type: str = "") -> AudioBuffer:
        return AudioBuffer(pcm_bytes=b"\x00\x00" * 2000)

    monkeypatch.setattr("remote.gateway.app.ingest_upload", _long_buffer)

    async def _upload() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/transcribe",
                files={"file": ("a.wav", _wav_bytes(), "audio/wav")},
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.status_code

    assert asyncio.run(_upload()) == 413
    sessions.submit_remote.assert_not_called()


async def _access_json(app) -> dict:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/access")
        assert response.status_code == 200
        return response.json()


def test_access_endpoint_does_not_expose_pin() -> None:
    sessions = MagicMock()
    pairing = PairingManager(bootstrap_secret=False)
    pairing.issue_pin()
    app = create_app(sessions, pairing=pairing)
    body = asyncio.run(_access_json(app))
    assert "pin" not in body
    assert body.get("pwa") == "/pwa/"
