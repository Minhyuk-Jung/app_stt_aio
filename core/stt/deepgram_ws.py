"""Deepgram WebSocket real-time streaming client (C2 §6.3).

Uses only Python standard library (socket + ssl) for RFC 6455 WebSocket.
No external websocket package required.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import socket
import ssl
import struct
from collections.abc import Iterator
from urllib.parse import urlencode

from core.stt.errors import AuthenticationError, NetworkError, TranscriptionError
from core.stt.types import STTChunkIterator, STTOptions, STTSegment

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "api.deepgram.com"
_DEFAULT_PORT = 443
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# RFC 6455 opcodes (module-level so stream_via_websocket can use them without
# referencing _MinimalWebSocket — avoids breakage when the class is patched in tests)
_OPCODE_TEXT = 0x1
_OPCODE_BINARY = 0x2

# Deepgram stream response types
_TYPE_RESULTS = "Results"
_TYPE_ERROR = "Error"
_TYPE_METADATA = "Metadata"
_TYPE_SPEECH_STARTED = "SpeechStarted"
_TYPE_UTTERANCE_END = "UtteranceEnd"


class _MinimalWebSocket:
    """Minimal RFC 6455 WebSocket client over TLS (client-to-server only).

    Supports:
    - Binary + text frames (send and receive)
    - Masking (required for client → server)
    - Ping/pong (auto-responds to server pings)
    - Close frame handling
    """

    OPCODE_TEXT = 0x1
    OPCODE_BINARY = 0x2
    OPCODE_CLOSE = 0x8
    OPCODE_PING = 0x9
    OPCODE_PONG = 0xA

    def __init__(
        self,
        host: str,
        port: int,
        path: str,
        extra_headers: dict[str, str],
        connect_timeout: float = 10.0,
        recv_timeout: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._path = path
        self._extra_headers = extra_headers
        self._connect_timeout = connect_timeout
        self._recv_timeout = recv_timeout
        self._sock: ssl.SSLSocket | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open TLS connection and perform WebSocket upgrade handshake."""
        raw = socket.create_connection((self._host, self._port), timeout=self._connect_timeout)
        ctx = ssl.create_default_context()
        wrapped = ctx.wrap_socket(raw, server_hostname=self._host)
        wrapped.settimeout(self._recv_timeout)
        self._sock = wrapped
        self._handshake()

    def _handshake(self) -> None:
        nonce_bytes = os.urandom(16)
        key = base64.b64encode(nonce_bytes).decode()

        request = (
            f"GET {self._path} HTTP/1.1\r\n"
            f"Host: {self._host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
        )
        for k, v in self._extra_headers.items():
            request += f"{k}: {v}\r\n"
        request += "\r\n"

        if self._sock is None:
            raise RuntimeError("WebSocket socket not initialized before handshake")
        self._sock.sendall(request.encode())

        # Read until blank line separates headers from body
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise NetworkError("WebSocket handshake: server closed connection")
            response += chunk

        first_line = response.split(b"\r\n")[0].decode(errors="replace")
        if "401" in first_line or "403" in first_line:
            raise AuthenticationError(f"Deepgram WebSocket: authentication failed ({first_line})")
        if "101" not in first_line:
            raise NetworkError(f"WebSocket handshake failed: {first_line}")

        # Verify Sec-WebSocket-Accept (RFC 6455 §4.1)
        expected = base64.b64encode(
            hashlib.sha1((key + _WS_GUID).encode()).digest()
        ).decode()
        header_block = response.split(b"\r\n\r\n")[0].decode(errors="replace")
        if expected not in header_block:
            raise NetworkError("WebSocket handshake: Sec-WebSocket-Accept mismatch")

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._send_frame(self.OPCODE_CLOSE, b"")
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    # ------------------------------------------------------------------
    # Send helpers
    # ------------------------------------------------------------------

    def send_binary(self, data: bytes) -> None:
        self._send_frame(self.OPCODE_BINARY, data)

    def send_text(self, text: str) -> None:
        self._send_frame(self.OPCODE_TEXT, text.encode("utf-8"))

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        """Encode a masked WebSocket frame (masking is required client → server)."""
        if self._sock is None:
            raise RuntimeError("WebSocket is not connected")
        fin_opcode = 0x80 | opcode
        length = len(payload)
        mask_key = os.urandom(4)

        if length < 126:
            length_bytes = bytes([0x80 | length])
        elif length < 65536:
            length_bytes = struct.pack("!BH", 0x80 | 126, length)
        else:
            length_bytes = struct.pack("!BQ", 0x80 | 127, length)

        masked_payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        frame = bytes([fin_opcode]) + length_bytes + mask_key + masked_payload
        self._sock.sendall(frame)

    # ------------------------------------------------------------------
    # Receive helpers
    # ------------------------------------------------------------------

    def recv_message(self) -> tuple[int, bytes] | None:
        """Receive one complete WebSocket frame.

        Returns ``(opcode, payload)`` or ``None`` when the server closed the
        connection (CLOSE frame or socket EOF).
        Automatically responds to PING frames.
        """
        if self._sock is None:
            return None
        try:
            header = self._recv_exact(2)
        except (OSError, ConnectionResetError, EOFError):
            return None

        opcode = header[0] & 0x0F
        masked = bool(header[1] & 0x80)
        raw_length = header[1] & 0x7F

        if raw_length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif raw_length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        else:
            length = raw_length

        mask_key = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length)
        if masked:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        if opcode == self.OPCODE_PING:
            self._send_frame(self.OPCODE_PONG, payload)
            return self.recv_message()

        if opcode == self.OPCODE_CLOSE:
            return None

        return opcode, payload

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise EOFError("connection closed mid-frame")
            buf.extend(chunk)
        return bytes(buf)


# ---------------------------------------------------------------------------
# Deepgram streaming helper
# ---------------------------------------------------------------------------

def stream_via_websocket(
    api_key: str,
    audio_chunks: STTChunkIterator,
    options: STTOptions,
    *,
    model: str,
    host: str = _DEFAULT_HOST,
    port: int = _DEFAULT_PORT,
    connect_timeout: float = 10.0,
    recv_timeout: float = 30.0,
) -> Iterator[STTSegment]:
    """Send audio to Deepgram live-streaming endpoint and yield final segments.

    Protocol:
    1. Open wss://api.deepgram.com/v1/listen with query params.
    2. Send audio as binary WebSocket frames (raw linear16 PCM).
    3. Send ``{"type": "CloseStream"}`` text frame to signal end of audio.
    4. Yield ``STTSegment`` for each ``is_final=true`` Results message.
    5. Stop when ``speech_final=true`` or connection closes.

    C2 §6.3 — real streaming path for Deepgram.
    """
    language = options.language if options.language != "auto" else "ko"
    params: dict[str, str] = {
        "model": model,
        "language": language,
        "punctuate": "true",
        "smart_format": "true",
        "encoding": "linear16",
        "sample_rate": "16000",
        "channels": "1",
    }
    if options.initial_prompt:
        params["keywords"] = options.initial_prompt

    path = f"/v1/listen?{urlencode(params)}"

    ws = _MinimalWebSocket(
        host=host,
        port=port,
        path=path,
        extra_headers={"Authorization": f"Token {api_key}"},
        connect_timeout=connect_timeout,
        recv_timeout=recv_timeout,
    )

    try:
        try:
            ws.connect()
        except AuthenticationError:
            raise
        except OSError as exc:
            raise NetworkError(f"Deepgram WebSocket connect failed: {exc}") from exc

        # Send all audio chunks (typically one VAD segment)
        for chunk in audio_chunks:
            if chunk:
                ws.send_binary(chunk)

        # Signal end of audio stream
        ws.send_text(json.dumps({"type": "CloseStream"}))

        # Receive transcript messages until the stream closes
        while True:
            result = ws.recv_message()
            if result is None:
                break

            opcode, payload = result
            if opcode != _OPCODE_TEXT:
                continue

            try:
                msg = json.loads(payload.decode("utf-8"))
            except json.JSONDecodeError:
                logger.warning("Deepgram: non-JSON frame received")
                continue

            msg_type = msg.get("type", "")

            if msg_type == _TYPE_ERROR:
                desc = msg.get("description", "unknown error")
                variant = msg.get("variant", "")
                raise TranscriptionError(f"Deepgram stream error ({variant}): {desc}")

            if msg_type == _TYPE_RESULTS:
                channel = msg.get("channel", {})
                alternatives = channel.get("alternatives", [])
                if not alternatives:
                    continue

                text = str(alternatives[0].get("transcript", "")).strip()
                is_final: bool = bool(msg.get("is_final", False))
                speech_final: bool = bool(msg.get("speech_final", False))
                start_ms = int(float(msg.get("start", 0)) * 1000)
                duration_ms = int(float(msg.get("duration", 0)) * 1000)

                if text and is_final:
                    yield STTSegment(
                        text=text,
                        is_final=True,
                        start_ms=start_ms,
                        end_ms=start_ms + duration_ms,
                    )

                if speech_final:
                    break

            elif msg_type in (_TYPE_METADATA, _TYPE_SPEECH_STARTED, _TYPE_UTTERANCE_END):
                logger.debug("Deepgram event: %s", msg_type)

    except (AuthenticationError, TranscriptionError, NetworkError):
        raise
    except OSError as exc:
        raise NetworkError(f"Deepgram WebSocket error: {exc}") from exc
    finally:
        ws.close()
