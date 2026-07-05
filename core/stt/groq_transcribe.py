"""Groq OpenAI-compatible transcription API (C2)."""

from __future__ import annotations

from core.stt.openai_transcribe import OpenAITranscribeProvider

_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
_DEFAULT_MODEL = "whisper-large-v3"


class GroqTranscribeProvider(OpenAITranscribeProvider):
    """Batch transcription via Groq /openai/v1/audio/transcriptions."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
        timeout_sec: float = 60.0,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_sec=timeout_sec,
        )

    @property
    def provider_id(self) -> str:
        return "groq_transcribe"
