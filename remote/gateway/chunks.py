"""In-memory chunked upload assembly (C15 §6.3, §7)."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

MAX_CHUNK_SESSIONS = 32
CHUNK_SESSION_TTL_SEC = 600


@dataclass
class _ChunkSession:
    parts: dict[int, bytes] = field(default_factory=dict)
    content_type: str = "application/octet-stream"
    created_at: float = field(default_factory=time.time)
    total_bytes: int = 0


class ChunkAssembler:
    """Assemble ordered upload parts before ingest (single-process gateway)."""

    def __init__(self, *, max_bytes: int) -> None:
        self._max_bytes = max_bytes
        self._lock = threading.Lock()
        self._sessions: dict[str, _ChunkSession] = {}

    def create_upload_id(self) -> str:
        self._purge_expired()
        upload_id = uuid.uuid4().hex
        with self._lock:
            if len(self._sessions) >= MAX_CHUNK_SESSIONS:
                oldest = min(self._sessions, key=lambda k: self._sessions[k].created_at)
                del self._sessions[oldest]
            self._sessions[upload_id] = _ChunkSession()
        return upload_id

    def add_part(
        self,
        upload_id: str,
        *,
        chunk_index: int,
        data: bytes,
        content_type: str,
        is_final: bool,
    ) -> bytes | None:
        if chunk_index < 0:
            raise ValueError("chunk_index must be >= 0")
        if not data and not is_final:
            raise ValueError("empty chunk")
        self._purge_expired()
        with self._lock:
            session = self._sessions.get(upload_id)
            if session is None:
                raise KeyError(upload_id)
            if chunk_index in session.parts:
                session.total_bytes -= len(session.parts[chunk_index])
                del session.parts[chunk_index]
            session.total_bytes += len(data)
            if session.total_bytes > self._max_bytes:
                del self._sessions[upload_id]
                raise ValueError("upload too large")
            if data:
                session.parts[chunk_index] = data
            if content_type:
                session.content_type = content_type
            if not is_final:
                return None
            if not session.parts:
                del self._sessions[upload_id]
                raise ValueError("no chunks received")
            indices = sorted(session.parts)
            if indices != list(range(len(indices))):
                del self._sessions[upload_id]
                raise ValueError("incomplete chunk sequence")
            ordered = [session.parts[i] for i in indices]
            payload = b"".join(ordered)
            del self._sessions[upload_id]
            return payload

    def _purge_expired(self) -> None:
        cutoff = time.time() - CHUNK_SESSION_TTL_SEC
        with self._lock:
            expired = [key for key, sess in self._sessions.items() if sess.created_at < cutoff]
            for key in expired:
                del self._sessions[key]
