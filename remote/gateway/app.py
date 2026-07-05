"""C15 Remote Gateway — FastAPI recording endpoint with pairing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from remote.gateway.chunks import ChunkAssembler
from remote.gateway.ingest import ingest_upload
from remote.gateway.pairing import PairingManager

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 32 * 1024 * 1024
MAX_REMOTE_DURATION_MS = 600_000  # 10 minutes (C15 §6.4)


def resolve_pwa_dir() -> Path:
    """Return PWA static directory (dev source tree or PyInstaller bundle)."""
    from core.runtime import bundle_root, is_frozen

    if is_frozen():
        root = bundle_root()
        if root is not None:
            bundled = root / "remote" / "gateway" / "pwa"
            if bundled.is_dir():
                return bundled
    return Path(__file__).resolve().parent / "pwa"

try:
    from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
    from fastapi.responses import JSONResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel

    class PairRequest(BaseModel):
        pin: str

    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

if TYPE_CHECKING:
    from app.session.session_manager import SessionManager


def create_app(
    session_manager: SessionManager,
    *,
    pairing: PairingManager | None = None,
):
    """Build a FastAPI app that accepts remote audio uploads."""
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI is required for RemoteGateway. pip install fastapi uvicorn"
        )

    manager = pairing or PairingManager()
    chunk_assembler = ChunkAssembler(max_bytes=MAX_UPLOAD_BYTES)
    app = FastAPI(title="STT-AIO Remote Gateway", version="0.4.0")
    pwa_dir = resolve_pwa_dir()

    def _require_token(authorization: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="missing token")
        token = authorization[7:].strip()
        if not manager.verify_token(token):
            raise HTTPException(status_code=401, detail="invalid token")
        return token

    def _submit_audio(data: bytes, content_type: str) -> JSONResponse:
        if not data:
            return JSONResponse({"error": "empty audio"}, status_code=400)
        if len(data) > MAX_UPLOAD_BYTES:
            return JSONResponse({"error": "file too large"}, status_code=413)
        try:
            buffer = ingest_upload(data, content_type=content_type or "")
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        if buffer.duration_ms > MAX_REMOTE_DURATION_MS:
            return JSONResponse({"error": "recording too long"}, status_code=413)
        session_id = session_manager.submit_remote(buffer)
        return JSONResponse({"session_id": session_id, "status": "processing"})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/access")
    def access_info() -> dict[str, str]:
        """Public status only — PIN is never exposed (C15 §9)."""
        return {"pwa": "/pwa/", "status": "ok"}

    @app.post("/api/v1/pair")
    def pair(req: PairRequest) -> JSONResponse:
        if manager.is_locked_out():
            return JSONResponse({"error": "too many attempts"}, status_code=429)
        token = manager.pair(req.pin)
        if token is None:
            if manager.is_locked_out():
                return JSONResponse({"error": "too many attempts"}, status_code=429)
            return JSONResponse({"error": "invalid pin"}, status_code=403)
        return JSONResponse({"token": token})

    @app.post("/api/v1/transcribe/chunks/init")
    def init_chunk_upload(_token: str = Depends(_require_token)) -> JSONResponse:
        upload_id = chunk_assembler.create_upload_id()
        return JSONResponse({"upload_id": upload_id})

    @app.post("/api/v1/transcribe/chunk")
    async def transcribe_chunk(
        upload_id: str = Form(...),
        chunk_index: int = Form(...),
        is_final: bool = Form(False),
        file: UploadFile = File(...),
        _token: str = Depends(_require_token),
    ) -> JSONResponse:
        data = await file.read()
        try:
            payload = chunk_assembler.add_part(
                upload_id,
                chunk_index=chunk_index,
                data=data,
                content_type=file.content_type or "",
                is_final=is_final,
            )
        except KeyError:
            return JSONResponse({"error": "unknown upload_id"}, status_code=404)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        if payload is None:
            return JSONResponse({"status": "chunk_accepted"})
        return _submit_audio(payload, file.content_type or "")

    @app.post("/api/v1/transcribe")
    async def transcribe(
        file: UploadFile = File(...),
        _token: str = Depends(_require_token),
    ) -> JSONResponse:
        data = await file.read()
        return _submit_audio(data, file.content_type or "")

    if pwa_dir.is_dir():
        app.mount("/pwa", StaticFiles(directory=str(pwa_dir), html=True), name="pwa")
    else:
        logger.warning("PWA directory missing: %s", pwa_dir)

    @app.get("/")
    def root():
        return RedirectResponse(url="/pwa/")

    return app
