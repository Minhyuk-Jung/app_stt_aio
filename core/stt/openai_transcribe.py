"""Cloud STT via OpenAI-compatible transcription API (C2)."""

from __future__ import annotations

import logging
import uuid

from core.audio.format import AudioBuffer
from core.stt.audio_adapter import audio_buffer_to_wav_bytes
from core.stt.base import STTProvider
from core.stt.errors import AuthenticationError
from core.stt.http_util import request_multipart_json
from core.stt.types import CostType, STTCapabilities, STTOptions, STTResult

logger = logging.getLogger(__name__)

_PROVIDER_ID = "openai_transcribe"


class OpenAITranscribeProvider(STTProvider):
    """Batch transcription using /v1/audio/transcriptions."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str = "whisper-1",
        timeout_sec: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_sec = timeout_sec

    @property
    def provider_id(self) -> str:
        return _PROVIDER_ID

    def capabilities(self) -> STTCapabilities:
        return STTCapabilities(
            supports_streaming=False,
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
            raise AuthenticationError("OpenAI-compatible STT requires an API key")

        wav_bytes = audio_buffer_to_wav_bytes(audio)
        boundary = f"----stt-aio-{uuid.uuid4().hex}"
        body = self._build_multipart(boundary, wav_bytes, opts)
        payload = request_multipart_json(
            f"{self._base_url}/audio/transcriptions",
            body=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            timeout=self._timeout_sec,
        )

        text = str(payload.get("text", ""))
        language = str(payload.get("language") or opts.language or "ko")
        return STTResult(text=text, language=language, provider_id=self.provider_id)

    def _build_multipart(
        self,
        boundary: str,
        wav_bytes: bytes,
        options: STTOptions,
    ) -> bytes:
        parts: list[bytes] = []
        fields: dict[str, str] = {
            "model": self._model,
            "language": options.language,
        }
        if options.initial_prompt:
            fields["prompt"] = options.initial_prompt
        for name, value in fields.items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            parts.append(value.encode("utf-8"))
            parts.append(b"\r\n")
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            b'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
            b"Content-Type: audio/wav\r\n\r\n"
        )
        parts.append(wav_bytes)
        parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return b"".join(parts)

    def warmup(self) -> None:
        return

    def close(self) -> None:
        return
