"""Managed STT provider lifecycle and transcription entry (C2 + C11)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.audio.format import AudioBuffer
from core.stt import STTOptions, STTProvider, STTResult, create_provider
from core.stt.errors import AuthenticationError, ProviderNotFoundError, STTError
from core.stt.registry import resolve_provider_id

if TYPE_CHECKING:
    from app.config.config import Config

logger = logging.getLogger(__name__)

_LOCAL_PROVIDER_ID = "faster_whisper_local"


class STTProviderSession:
    """Holds a lazily created provider and refreshes on config changes (C2 §6.4)."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._provider: STTProvider | None = None

    @property
    def provider(self) -> STTProvider:
        if self._provider is None:
            self._provider = self._config.create_stt_provider()
        return self._provider

    def refresh(self) -> STTProvider:
        if self._provider is not None:
            self._provider.close()
        self._provider = self._config.create_stt_provider()
        logger.info("STT provider refreshed: %s", self._provider.provider_id)
        return self._provider

    def transcribe(
        self,
        audio: AudioBuffer,
        options: STTOptions | None = None,
    ) -> STTResult:
        return self._transcribe_with_fallback(
            audio,
            options,
            use_stream=False,
        )

    def transcribe_segment(
        self,
        audio: AudioBuffer,
        options: STTOptions | None = None,
    ) -> STTResult:
        """Transcribe a VAD segment; uses stream() when the provider supports it (C2 §6.3)."""
        return self._transcribe_with_fallback(
            audio,
            options,
            use_stream=True,
        )

    def _transcribe_with_fallback(
        self,
        audio: AudioBuffer,
        options: STTOptions | None,
        *,
        use_stream: bool,
    ) -> STTResult:
        opts = options or self._config.get_stt_options()
        try:
            return self._transcribe_once(audio, opts, use_stream=use_stream)
        except STTError as exc:
            if not self._should_fallback(exc):
                raise
            logger.warning(
                "STT provider '%s' failed (%s); falling back to local",
                self.provider.provider_id,
                exc,
            )
            fallback = self._create_local_fallback()
            try:
                return fallback.transcribe(audio, opts)
            finally:
                fallback.close()

    def _transcribe_once(
        self,
        audio: AudioBuffer,
        opts: STTOptions,
        *,
        use_stream: bool,
    ) -> STTResult:
        provider = self.provider
        if use_stream and provider.capabilities().supports_streaming:
            try:
                segments = list(
                    provider.stream(iter([audio.pcm_bytes]), opts)
                )
            except NotImplementedError:
                segments = []
            if segments:
                text = " ".join(seg.text.strip() for seg in segments if seg.text).strip()
                language = opts.language
                return STTResult(
                    text=text,
                    language=language,
                    duration_ms=audio.duration_ms,
                    provider_id=provider.provider_id,
                )
        return provider.transcribe(audio, opts)

    def warmup(self) -> None:
        self.provider.warmup()

    def close(self) -> None:
        if self._provider is not None:
            self._provider.close()
            self._provider = None

    def _should_fallback(self, error: STTError) -> bool:
        if isinstance(error, AuthenticationError):
            return False
        if not self._config.get("stt.fallback_to_local"):
            return False
        provider_id = self.provider.provider_id
        if provider_id == _LOCAL_PROVIDER_ID:
            return False
        try:
            return resolve_provider_id(provider_id) != _LOCAL_PROVIDER_ID
        except ProviderNotFoundError:
            return True

    def _create_local_fallback(self) -> STTProvider:
        return create_provider(
            _LOCAL_PROVIDER_ID,
            models_dir=self._config.model_manager.models_dir,
            model_id=self._config.get("stt.model"),
        )
