"""Tests for Deepgram WebSocket streaming (C2 §6.3)."""

from __future__ import annotations

import json
import struct
from unittest.mock import MagicMock, patch

import pytest

from core.stt.deepgram_ws import _OPCODE_TEXT, _MinimalWebSocket, stream_via_websocket
from core.stt.deepgram_transcribe import DeepgramTranscribeProvider
from core.stt.errors import AuthenticationError, NetworkError, TranscriptionError
from core.stt.types import STTOptions


# ---------------------------------------------------------------------------
# _MinimalWebSocket unit tests (frame encoding / decoding)
# ---------------------------------------------------------------------------


def test_ws_send_frame_binary_masked() -> None:
    """Binary frames sent by client must be masked (RFC 6455 §5.3)."""
    ws = _MinimalWebSocket("api.deepgram.com", 443, "/v1/listen", {})
    sent_bytes: bytearray = bytearray()

    mock_sock = MagicMock()
    mock_sock.sendall.side_effect = lambda b: sent_bytes.extend(b)
    ws._sock = mock_sock

    payload = b"\x01\x02\x03\x04"
    ws.send_binary(payload)

    # First byte: FIN=1, opcode=2 (binary) → 0x82
    assert sent_bytes[0] == 0x82
    # Second byte: MASK bit set → bit 7 == 1
    assert sent_bytes[1] & 0x80 == 0x80
    # Payload length in low 7 bits
    assert sent_bytes[1] & 0x7F == len(payload)


def test_ws_send_frame_text_masked() -> None:
    """Text frames must also be masked (RFC 6455 §5.3)."""
    ws = _MinimalWebSocket("api.deepgram.com", 443, "/v1/listen", {})
    sent_bytes: bytearray = bytearray()
    mock_sock = MagicMock()
    mock_sock.sendall.side_effect = lambda b: sent_bytes.extend(b)
    ws._sock = mock_sock

    ws.send_text("hello")

    assert sent_bytes[0] == 0x81  # FIN + TEXT opcode
    assert sent_bytes[1] & 0x80 == 0x80  # masked


def test_ws_recv_message_text_frame() -> None:
    """Receive an unmasked text frame from server."""
    payload = b'{"type":"Metadata"}'
    # Server sends: FIN + opcode TEXT (0x81), length byte, payload (no mask)
    frame = bytes([0x81, len(payload)]) + payload

    ws = _MinimalWebSocket("api.deepgram.com", 443, "/v1/listen", {})
    mock_sock = MagicMock()
    mock_sock.recv.side_effect = [frame[:1], frame[1:2], frame[2:]]
    ws._sock = mock_sock

    # Patch _recv_exact to read from frame bytes sequentially
    idx = [0]
    def fake_recv_exact(n: int) -> bytes:
        chunk = frame[idx[0]:idx[0] + n]
        idx[0] += n
        return chunk

    ws._recv_exact = fake_recv_exact  # type: ignore[method-assign]
    result = ws.recv_message()
    assert result is not None
    opcode, data = result
    assert opcode == _MinimalWebSocket.OPCODE_TEXT
    assert data == payload


def test_ws_recv_message_returns_none_on_close_frame() -> None:
    """CLOSE frame from server causes recv_message to return None."""
    frame = bytes([0x88, 0x00])  # FIN + CLOSE opcode, no payload

    ws = _MinimalWebSocket("api.deepgram.com", 443, "/v1/listen", {})
    idx = [0]

    def fake_recv_exact(n: int) -> bytes:
        chunk = frame[idx[0]:idx[0] + n]
        idx[0] += n
        return chunk

    ws._sock = MagicMock()
    ws._sock.sendall = MagicMock()
    ws._recv_exact = fake_recv_exact  # type: ignore[method-assign]
    result = ws.recv_message()
    assert result is None


def test_ws_recv_message_auto_pong() -> None:
    """PING frame should trigger a PONG reply and then recurse for next frame."""
    ping_payload = b"keepalive"
    text_payload = b'{"type":"Metadata"}'

    ping_frame = bytes([0x89, len(ping_payload)]) + ping_payload
    text_frame = bytes([0x81, len(text_payload)]) + text_payload
    all_bytes = ping_frame + text_frame

    ws = _MinimalWebSocket("api.deepgram.com", 443, "/v1/listen", {})
    sent: bytearray = bytearray()
    mock_sock = MagicMock()
    mock_sock.sendall.side_effect = lambda b: sent.extend(b)
    ws._sock = mock_sock

    idx = [0]

    def fake_recv_exact(n: int) -> bytes:
        chunk = all_bytes[idx[0]:idx[0] + n]
        idx[0] += n
        return chunk

    ws._recv_exact = fake_recv_exact  # type: ignore[method-assign]
    result = ws.recv_message()

    # Should have sent PONG (opcode 0x8A)
    assert sent[0] == 0x8A
    # Should return the text frame after the PING
    assert result is not None
    assert result[1] == text_payload


# ---------------------------------------------------------------------------
# stream_via_websocket integration (mocked WebSocket)
# ---------------------------------------------------------------------------

def _make_deepgram_results(text: str, *, is_final: bool, speech_final: bool) -> bytes:
    msg = {
        "type": "Results",
        "start": 0.0,
        "duration": 1.0,
        "is_final": is_final,
        "speech_final": speech_final,
        "channel": {
            "alternatives": [{"transcript": text, "confidence": 0.99}]
        },
    }
    return json.dumps(msg).encode("utf-8")


def _make_recv_sequence(*text_payloads: bytes, close_at_end: bool = True):
    """Return a side_effect list for recv_message mock."""
    results = [(_OPCODE_TEXT, p) for p in text_payloads]
    if close_at_end:
        results.append(None)
    return results


def test_stream_via_websocket_yields_final_segment() -> None:
    """stream_via_websocket yields STTSegment for is_final=True results."""
    interim = _make_deepgram_results("안녕", is_final=False, speech_final=False)
    final = _make_deepgram_results("안녕하세요", is_final=True, speech_final=True)

    with patch("core.stt.deepgram_ws._MinimalWebSocket") as MockWS:
        instance = MockWS.return_value
        instance.recv_message.side_effect = _make_recv_sequence(interim, final)

        segments = list(
            stream_via_websocket(
                api_key="dg-test",
                audio_chunks=iter([b"\x00" * 100]),
                options=STTOptions(language="ko"),
                model="nova-2",
            )
        )

    assert len(segments) == 1
    assert segments[0].text == "안녕하세요"
    assert segments[0].is_final is True


def test_stream_via_websocket_skips_interim_segments() -> None:
    """is_final=False segments are NOT yielded."""
    interim1 = _make_deepgram_results("안녕", is_final=False, speech_final=False)
    interim2 = _make_deepgram_results("안녕하세요", is_final=False, speech_final=False)
    final = _make_deepgram_results("안녕하세요 반갑습니다", is_final=True, speech_final=True)

    with patch("core.stt.deepgram_ws._MinimalWebSocket") as MockWS:
        instance = MockWS.return_value
        instance.recv_message.side_effect = _make_recv_sequence(interim1, interim2, final)

        segments = list(
            stream_via_websocket(
                api_key="dg-test",
                audio_chunks=iter([b"\x00" * 200]),
                options=STTOptions(language="ko"),
                model="nova-2",
            )
        )

    assert len(segments) == 1
    assert segments[0].text == "안녕하세요 반갑습니다"


def test_stream_via_websocket_raises_on_error_message() -> None:
    """Deepgram Error message raises TranscriptionError."""
    error_msg = json.dumps({
        "type": "Error",
        "description": "Invalid audio format",
        "variant": "INVALID_ENCODING",
    }).encode("utf-8")

    with patch("core.stt.deepgram_ws._MinimalWebSocket") as MockWS:
        instance = MockWS.return_value
        instance.recv_message.side_effect = [
                (_OPCODE_TEXT, error_msg),
                None,
            ]

        with pytest.raises(TranscriptionError, match="INVALID_ENCODING"):
            list(
                stream_via_websocket(
                    api_key="dg-test",
                    audio_chunks=iter([b"\x00" * 100]),
                    options=STTOptions(language="ko"),
                    model="nova-2",
                )
            )


def test_stream_via_websocket_empty_transcript_not_yielded() -> None:
    """Empty transcript is not yielded even if is_final=True."""
    empty = _make_deepgram_results("", is_final=True, speech_final=True)

    with patch("core.stt.deepgram_ws._MinimalWebSocket") as MockWS:
        instance = MockWS.return_value
        instance.recv_message.side_effect = _make_recv_sequence(empty)

        segments = list(
            stream_via_websocket(
                api_key="dg-test",
                audio_chunks=iter([b"\x00" * 100]),
                options=STTOptions(language="ko"),
                model="nova-2",
            )
        )

    assert segments == []


def test_stream_via_websocket_connect_failure_raises_network_error() -> None:
    """OSError during connect() raises NetworkError."""
    with patch("core.stt.deepgram_ws._MinimalWebSocket") as MockWS:
        instance = MockWS.return_value
        instance.connect.side_effect = OSError("connection refused")

        with pytest.raises(NetworkError, match="connect failed"):
            list(
                stream_via_websocket(
                    api_key="dg-test",
                    audio_chunks=iter([b"\x00" * 100]),
                    options=STTOptions(language="ko"),
                    model="nova-2",
                )
            )


# ---------------------------------------------------------------------------
# DeepgramTranscribeProvider with stream() (C2 §6.3)
# ---------------------------------------------------------------------------

def test_deepgram_provider_supports_streaming() -> None:
    provider = DeepgramTranscribeProvider(api_key="dg-test")
    assert provider.capabilities().supports_streaming is True


def test_deepgram_provider_stream_requires_api_key() -> None:
    provider = DeepgramTranscribeProvider(api_key=None)
    with pytest.raises(AuthenticationError):
        list(provider.stream(iter([b"\x00" * 100])))


def test_deepgram_provider_stream_delegates_to_ws() -> None:
    """stream() on DeepgramTranscribeProvider delegates to stream_via_websocket."""
    final = _make_deepgram_results("테스트 결과", is_final=True, speech_final=True)

    with patch("core.stt.deepgram_ws._MinimalWebSocket") as MockWS:
        instance = MockWS.return_value
        instance.recv_message.side_effect = _make_recv_sequence(final)

        provider = DeepgramTranscribeProvider(api_key="dg-key", model="nova-2")
        segments = list(provider.stream(iter([b"\x00" * 320]), STTOptions(language="ko")))

    assert len(segments) == 1
    assert segments[0].text == "테스트 결과"


def test_deepgram_provider_stream_auto_language_maps_to_ko() -> None:
    """language='auto' should map to 'ko' for Deepgram."""
    final = _make_deepgram_results("한국어", is_final=True, speech_final=True)

    with patch("core.stt.deepgram_ws._MinimalWebSocket") as MockWS:
        instance = MockWS.return_value
        instance.recv_message.side_effect = _make_recv_sequence(final)

        provider = DeepgramTranscribeProvider(api_key="dg-key")
        segments = list(provider.stream(iter([b"\x00" * 320]), STTOptions(language="auto")))

    # Verify the WS path param contained language=ko
    ws_call_args = MockWS.call_args
    path_arg = ws_call_args.kwargs.get("path", "") or ws_call_args.args[2]
    assert "language=ko" in path_arg


def test_registry_deepgram_stream_alias_resolves() -> None:
    """'deepgram_stream' alias resolves to 'deepgram_transcribe'."""
    from core.stt.registry import resolve_provider_id

    assert resolve_provider_id("deepgram_stream") == "deepgram_transcribe"
    assert resolve_provider_id("deepgram-stream") == "deepgram_transcribe"


# ---------------------------------------------------------------------------
# Bug-fix tests
# ---------------------------------------------------------------------------

def test_ws_send_frame_extended_length_2byte() -> None:
    """Payload 126..65535 bytes uses 2-byte extended length encoding."""
    ws = _MinimalWebSocket("api.deepgram.com", 443, "/v1/listen", {})
    sent_bytes: bytearray = bytearray()
    mock_sock = MagicMock()
    mock_sock.sendall.side_effect = lambda b: sent_bytes.extend(b)
    ws._sock = mock_sock

    payload = b"\xAB" * 200  # 200 bytes → requires extended length
    ws.send_binary(payload)

    # byte 0: FIN + BINARY (0x82)
    assert sent_bytes[0] == 0x82
    # byte 1: MASK + 126 (extended marker)
    assert sent_bytes[1] & 0x7F == 126
    assert sent_bytes[1] & 0x80 == 0x80  # mask bit
    # bytes 2-3: big-endian uint16 length
    actual_len = struct.unpack("!H", bytes(sent_bytes[2:4]))[0]
    assert actual_len == 200


def test_ws_send_frame_extended_length_8byte() -> None:
    """Payload > 65535 bytes uses 8-byte extended length encoding."""
    ws = _MinimalWebSocket("api.deepgram.com", 443, "/v1/listen", {})
    sent_bytes: bytearray = bytearray()
    mock_sock = MagicMock()
    mock_sock.sendall.side_effect = lambda b: sent_bytes.extend(b)
    ws._sock = mock_sock

    payload = b"\xCD" * 70000  # 70000 bytes → 8-byte length
    ws.send_binary(payload)

    assert sent_bytes[1] & 0x7F == 127
    actual_len = struct.unpack("!Q", bytes(sent_bytes[2:10]))[0]
    assert actual_len == 70000


def test_ws_host_extracted_from_custom_base_url() -> None:
    """stream() uses the host parsed from the configured base_url."""
    from core.stt.deepgram_transcribe import _ws_host_from_base_url

    assert _ws_host_from_base_url("https://custom.deepgram.example.com/v1/listen") == \
        "custom.deepgram.example.com"
    assert _ws_host_from_base_url("https://api.deepgram.com/v1/listen") == "api.deepgram.com"
    assert _ws_host_from_base_url("") == "api.deepgram.com"  # fallback


def test_deepgram_provider_stream_uses_base_url_host() -> None:
    """stream() passes host derived from base_url, not a hardcoded constant."""
    final = _make_deepgram_results("확인", is_final=True, speech_final=True)

    with patch("core.stt.deepgram_ws._MinimalWebSocket") as MockWS:
        instance = MockWS.return_value
        instance.recv_message.side_effect = _make_recv_sequence(final)

        provider = DeepgramTranscribeProvider(
            api_key="dg-key",
            base_url="https://eu.deepgram.com/v1/listen",
        )
        list(provider.stream(iter([b"\x00" * 100]), STTOptions(language="ko")))

    ws_call_kwargs = MockWS.call_args.kwargs
    assert ws_call_kwargs.get("host") == "eu.deepgram.com"


def test_ws_recv_message_on_closed_socket_returns_none() -> None:
    """recv_message returns None (not RuntimeError) when socket is None."""
    ws = _MinimalWebSocket("api.deepgram.com", 443, "/v1/listen", {})
    ws._sock = None  # simulate closed state
    result = ws.recv_message()
    assert result is None
