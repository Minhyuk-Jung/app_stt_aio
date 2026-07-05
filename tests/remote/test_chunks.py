"""Chunk upload tests (C15 §6.3)."""

from __future__ import annotations

import asyncio
import wave
from io import BytesIO
from unittest.mock import MagicMock

import httpx
import pytest

pytest.importorskip("fastapi")

from remote.gateway.app import create_app
from remote.gateway.chunks import ChunkAssembler
from remote.gateway.pairing import PairingManager


def _wav_bytes(*, duration_sec: float = 0.1) -> bytes:
    buf = BytesIO()
    frames = int(16000 * duration_sec)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


def test_chunk_assembler_orders_parts() -> None:
    assembler = ChunkAssembler(max_bytes=1024 * 1024)
    upload_id = assembler.create_upload_id()
    assembler.add_part(upload_id, chunk_index=1, data=b"world", content_type="audio/wav", is_final=False)
    payload = assembler.add_part(
        upload_id,
        chunk_index=0,
        data=b"hello",
        content_type="audio/wav",
        is_final=True,
    )
    assert payload == b"helloworld"


async def _chunk_upload_flow(app, token: str, audio: bytes) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        init = await client.post(
            "/api/v1/transcribe/chunks/init",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert init.status_code == 200
        upload_id = init.json()["upload_id"]
        mid = max(1, len(audio) // 2)
        part0 = await client.post(
            "/api/v1/transcribe/chunk",
            data={"upload_id": upload_id, "chunk_index": 0, "is_final": "false"},
            files={"file": ("a.wav", audio[:mid], "audio/wav")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert part0.status_code == 200
        return await client.post(
            "/api/v1/transcribe/chunk",
            data={"upload_id": upload_id, "chunk_index": 1, "is_final": "true"},
            files={"file": ("a.wav", audio[mid:], "audio/wav")},
            headers={"Authorization": f"Bearer {token}"},
        )


def test_chunk_assembler_rejects_gap_on_finalize() -> None:
    assembler = ChunkAssembler(max_bytes=1024 * 1024)
    upload_id = assembler.create_upload_id()
    assembler.add_part(upload_id, chunk_index=1, data=b"b", content_type="audio/wav", is_final=False)
    with pytest.raises(ValueError, match="incomplete chunk sequence"):
        assembler.add_part(upload_id, chunk_index=2, data=b"c", content_type="audio/wav", is_final=True)


def test_chunk_assembler_allows_chunk_retry() -> None:
    assembler = ChunkAssembler(max_bytes=1024 * 1024)
    upload_id = assembler.create_upload_id()
    assembler.add_part(upload_id, chunk_index=0, data=b"old", content_type="audio/wav", is_final=False)
    payload = assembler.add_part(
        upload_id,
        chunk_index=0,
        data=b"new",
        content_type="audio/wav",
        is_final=True,
    )
    assert payload == b"new"


async def _chunk_upload_missing_final(app, token: str) -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        init = await client.post(
            "/api/v1/transcribe/chunks/init",
            headers={"Authorization": f"Bearer {token}"},
        )
        upload_id = init.json()["upload_id"]
        res = await client.post(
            "/api/v1/transcribe/chunk",
            data={"upload_id": upload_id, "chunk_index": 1, "is_final": "true"},
            files={"file": ("a.wav", b"only", "audio/wav")},
            headers={"Authorization": f"Bearer {token}"},
        )
        return res.status_code


def test_chunk_upload_rejects_incomplete_sequence() -> None:
    sessions = MagicMock()
    pairing = PairingManager(bootstrap_secret=False)
    pin = pairing.issue_pin()
    token = pairing.pair(pin)
    assert token is not None
    app = create_app(sessions, pairing=pairing)
    status = asyncio.run(_chunk_upload_missing_final(app, token))
    assert status == 400
    sessions.submit_remote.assert_not_called()


def test_chunk_upload_e2e() -> None:
    sessions = MagicMock()
    sessions.submit_remote.return_value = "chunk-session"
    pairing = PairingManager(bootstrap_secret=False)
    pin = pairing.issue_pin()
    token = pairing.pair(pin)
    assert token is not None
    app = create_app(sessions, pairing=pairing)
    audio = _wav_bytes()
    response = asyncio.run(_chunk_upload_flow(app, token, audio))
    assert response.status_code == 200
    assert response.json()["session_id"] == "chunk-session"
    sessions.submit_remote.assert_called_once()


def test_large_upload_uses_multiple_chunks() -> None:
    sessions = MagicMock()
    sessions.submit_remote.return_value = "large-session"
    pairing = PairingManager(bootstrap_secret=False)
    pin = pairing.issue_pin()
    token = pairing.pair(pin)
    assert token is not None
    app = create_app(sessions, pairing=pairing)
    # >512KiB triggers multi-chunk path in PWA; server accepts any split size
    audio = _wav_bytes(duration_sec=20.0)
    assert len(audio) > 512 * 1024
    response = asyncio.run(_chunk_upload_flow(app, token, audio))
    assert response.status_code == 200
    assert response.json()["session_id"] == "large-session"
