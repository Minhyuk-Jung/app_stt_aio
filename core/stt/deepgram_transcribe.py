"""Deepgram listen API transcription — batch REST + WebSocket streaming (C2)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from urllib.parse import urlencode, urlparse

from core.audio.format import AudioBuffer
from core.stt.audio_adapter import audio_buffer_to_wav_bytes
from core.stt.base import STTProvider
from core.stt.errors import AuthenticationError, TranscriptionError
from core.stt.http_util import request_bytes
from core.stt.types import CostType, STTCapabilities, STTChunkIterator, STTOptions, STTResult, STTSegment

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.deepgram.com/v1/listen"
_DEFAULT_MODEL = "nova-2"


def _ws_host_from_base_url(base_url: str) -> str:
    """Extract hostname from the batch REST base_url for WebSocket consistency."""
    try:
        return urlparse(base_url).hostname or "api.deepgram.com"
    except Exception:  # noqa: BLE001
        return "api.deepgram.com"


class DeepgramTranscribeProvider(STTProvider):
    """Deepgram STT: batch via /v1/listen REST, streaming via WebSocket (C2 §6.3)."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
        timeout_sec: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_sec = timeout_sec

    @property
    def provider_id(self) -> str:
        return "deepgram_transcribe"

    def capabilities(self) -> STTCapabilities:
        return STTCapabilities(
            supports_streaming=True,
            languages=("ko", "en", "auto"),
            max_audio_sec=1800,
            needs_network=True,
            cost_type=CostType.PAID,
            gpu_optional=True,
        )

    def transcribe(
        self,
        audio: AudioBuffer,
        options: STTOptions | None = None,
    ) -> STTResult:
        opts = options or STTOptions()
        if not self._api_key:
            raise AuthenticationError("Deepgram STT requires an API key")

        wav_bytes = audio_buffer_to_wav_bytes(audio)
        language = opts.language if opts.language != "auto" else "ko"
        params: dict[str, str] = {
            "model": self._model,
            "language": language,
            "punctuate": "true",
            "smart_format": "true",
        }
        if opts.initial_prompt:
            params["keywords"] = opts.initial_prompt
        query = urlencode(params)
        url = f"{self._base_url}?{query}"
        raw = request_bytes(
            url,
            body=wav_bytes,
            headers={
                "Authorization": f"Token {self._api_key}",
                "Content-Type": "audio/wav",
            },
            timeout=self._timeout_sec,
        )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise TranscriptionError("Deepgram returned invalid JSON") from exc

        text = self._extract_transcript(payload)
        return STTResult(
            text=text,
            language=language,
            duration_ms=audio.duration_ms,
            provider_id=self.provider_id,
        )

    @staticmethod
    def _extract_transcript(payload: dict) -> str:
        try:
            channels = payload["results"]["channels"]
            alternatives = channels[0]["alternatives"]
            return str(alternatives[0].get("transcript", "")).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise TranscriptionError("Deepgram response missing transcript") from exc

    def stream(
        self,
        audio_chunks: STTChunkIterator,
        options: STTOptions | None = None,
    ) -> Iterator[STTSegment]:
        """Real-time transcription via Deepgram WebSocket (C2 §6.3).

        Sends raw linear16 PCM chunks and yields is_final=True segments.
        Uses the same host as the configured batch base_url for consistency.
        NetworkError propagates to STTProviderSession which handles local fallback.
        """
        if not self._api_key:
            raise AuthenticationError("Deepgram streaming requires an API key")

        from core.stt.deepgram_ws import stream_via_websocket

        opts = options or STTOptions()
        ws_host = _ws_host_from_base_url(self._base_url)
        yield from stream_via_websocket(
            api_key=self._api_key,
            audio_chunks=audio_chunks,
            options=opts,
            model=self._model,
            host=ws_host,
            recv_timeout=self._timeout_sec,
        )

    def warmup(self) -> None:
        return

    def close(self) -> None:
        return
