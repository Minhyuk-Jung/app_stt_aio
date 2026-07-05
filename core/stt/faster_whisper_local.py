"""Local faster-whisper STT provider (P1)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Iterator

from core.audio.format import AudioBuffer, STANDARD_CHANNELS, STANDARD_SAMPLE_RATE
from core.audio.resample import build_audio_buffer
from core.audio.level import compute_peak_rms
from core.models.resolver import resolve_whisper_model_path
from core.models.errors import ModelNotFoundError as ResolverModelNotFound
from core.stt.audio_adapter import audio_buffer_to_float32
from core.stt.base import STTProvider
from core.stt.errors import (
    AudioFormatError,
    ModelLoadError,
    ModelNotFoundError,
    ProviderBusyError,
    TranscriptionError,
)
from core.stt.types import (
    CostType,
    ProviderState,
    STTCapabilities,
    STTOptions,
    STTResult,
    STTSegment,
    STTSegmentResult,
)

logger = logging.getLogger(__name__)

_PROVIDER_ID = "faster_whisper_local"
_MAX_AUDIO_SEC = 600
_SILENCE_PEAK_THRESHOLD = 0.002


def _import_whisper_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ModelLoadError(
            "faster-whisper is not installed. "
            "Install with: pip install 'stt-aio[stt]'"
        ) from exc
    return WhisperModel


class FasterWhisperLocalProvider(STTProvider):
    """Batch transcription using faster-whisper (CTranslate2)."""

    def __init__(
        self,
        *,
        models_dir: Path,
        model_id: str = "base",
        device: str = "auto",
        compute_type: str = "default",
    ) -> None:
        self._models_dir = models_dir
        self._model_id = model_id
        self._device = device
        self._compute_type = compute_type
        self._model: Any | None = None
        self._model_path: str | None = None
        self._state = ProviderState.UNLOADED
        self._lock = threading.Lock()

    @property
    def provider_id(self) -> str:
        return _PROVIDER_ID

    @property
    def state(self) -> ProviderState:
        return self._state

    def capabilities(self) -> STTCapabilities:
        return STTCapabilities(
            supports_streaming=True,
            languages=("ko", "en", "ja", "zh", "auto"),
            max_audio_sec=_MAX_AUDIO_SEC,
            needs_network=False,
            cost_type=CostType.LOCAL,
            gpu_optional=True,
        )

    def warmup(self) -> None:
        self._ensure_model()

    def close(self) -> None:
        with self._lock:
            self._model = None
            self._model_path = None
            self._state = ProviderState.UNLOADED

    def transcribe(
        self,
        audio: AudioBuffer,
        options: STTOptions | None = None,
    ) -> STTResult:
        opts = options or STTOptions()
        if audio.duration_ms > self.capabilities().max_audio_sec * 1000:
            raise TranscriptionError(
                f"audio exceeds max length of {self.capabilities().max_audio_sec}s"
            )

        if audio.is_empty or self._is_silent(audio):
            return STTResult(
                text="",
                language=opts.language,
                segments=[],
                duration_ms=audio.duration_ms,
                provider_id=self.provider_id,
            )

        with self._lock:
            if self._state == ProviderState.BUSY:
                raise ProviderBusyError("transcription already in progress")
            self._state = ProviderState.BUSY

        try:
            return self._transcribe_unlocked(audio, opts)
        except Exception:
            self._restore_ready_after_failure()
            raise
        finally:
            with self._lock:
                if self._state == ProviderState.BUSY:
                    self._state = ProviderState.READY

    def stream(
        self,
        audio_chunks: Iterator[bytes],
        options: STTOptions | None = None,
    ) -> Iterator[STTSegment]:
        """Pseudo-streaming: each PCM chunk is a VAD segment (C2 §6.3)."""
        opts = options or STTOptions()
        with self._lock:
            if self._state == ProviderState.BUSY:
                raise ProviderBusyError("transcription already in progress")
            self._state = ProviderState.BUSY
        try:
            for chunk in audio_chunks:
                if not chunk:
                    continue
                audio = build_audio_buffer(
                    chunk,
                    sample_rate=STANDARD_SAMPLE_RATE,
                    channels=STANDARD_CHANNELS,
                )
                result = self._transcribe_unlocked(audio, opts)
                if not result.text.strip():
                    continue
                end_ms = result.duration_ms or audio.duration_ms
                if result.segments:
                    seg = result.segments[-1]
                    yield STTSegment(
                        text=seg.text,
                        is_final=True,
                        start_ms=seg.start_ms,
                        end_ms=seg.end_ms,
                    )
                else:
                    yield STTSegment(
                        text=result.text.strip(),
                        is_final=True,
                        start_ms=0,
                        end_ms=end_ms,
                    )
        except Exception:
            self._restore_ready_after_failure()
            raise
        finally:
            with self._lock:
                if self._state == ProviderState.BUSY:
                    self._state = ProviderState.READY

    def _transcribe_unlocked(self, audio: AudioBuffer, opts: STTOptions) -> STTResult:
        try:
            samples = audio_buffer_to_float32(audio)
        except AudioFormatError:
            raise

        model = self._ensure_model()
        initial_prompt = self._build_initial_prompt(opts)

        try:
            segments_iter, info = model.transcribe(
                samples,
                language=None if opts.language == "auto" else opts.language,
                initial_prompt=initial_prompt or None,
                beam_size=opts.beam_size,
                temperature=opts.temperature,
                task=opts.task,
                vad_filter=False,
            )
        except Exception as exc:
            raise TranscriptionError(f"faster-whisper transcription failed: {exc}") from exc

        segments: list[STTSegmentResult] = []
        text_parts: list[str] = []
        for segment in segments_iter:
            segment_text = segment.text.strip()
            if not segment_text:
                continue
            start_ms = int(segment.start * 1000)
            end_ms = int(segment.end * 1000)
            confidence = getattr(segment, "avg_logprob", None)
            segments.append(
                STTSegmentResult(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=segment_text,
                    confidence=float(confidence) if confidence is not None else None,
                )
            )
            text_parts.append(segment_text)

        language = getattr(info, "language", None) or opts.language
        text = " ".join(text_parts).strip()
        return STTResult(
            text=text,
            language=language,
            segments=segments,
            duration_ms=audio.duration_ms,
            provider_id=self.provider_id,
        )

    def _restore_ready_after_failure(self) -> None:
        with self._lock:
            if self._model is not None:
                self._state = ProviderState.READY
            else:
                self._state = ProviderState.UNLOADED

    @staticmethod
    def _is_silent(audio: AudioBuffer) -> bool:
        peak, _rms = compute_peak_rms(audio.pcm_bytes)
        return peak < _SILENCE_PEAK_THRESHOLD

    def _ensure_model(self):
        with self._lock:
            try:
                model_path = resolve_whisper_model_path(self._models_dir, self._model_id)
            except ResolverModelNotFound as exc:
                raise ModelNotFoundError(str(exc)) from exc

            if self._model is not None and self._model_path == model_path:
                return self._model

            previous_state = self._state
            if previous_state != ProviderState.BUSY:
                self._state = ProviderState.LOADING
            WhisperModel = _import_whisper_model()
            try:
                logger.info(
                    "Loading faster-whisper model '%s' (device=%s)",
                    model_path,
                    self._device,
                )
                self._model = WhisperModel(
                    model_path,
                    device=self._device,
                    compute_type=self._compute_type,
                )
                self._model_path = model_path
                self._state = ProviderState.READY
                return self._model
            except ModelNotFoundError:
                self._state = ProviderState.UNLOADED
                raise
            except Exception as exc:
                self._state = ProviderState.UNLOADED
                from core.diagnostics import report_error

                report_error(
                    exc,
                    context={
                        "component": "stt",
                        "model_path": model_path,
                        "device": self._device,
                    },
                )
                raise ModelLoadError(f"failed to load model '{model_path}': {exc}") from exc

    @staticmethod
    def _build_initial_prompt(opts: STTOptions) -> str:
        parts: list[str] = []
        if opts.initial_prompt.strip():
            parts.append(opts.initial_prompt.strip())
        if opts.hotwords:
            parts.append(", ".join(opts.hotwords))
        return ". ".join(parts)
