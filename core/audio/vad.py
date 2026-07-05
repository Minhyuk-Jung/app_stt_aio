"""VAD processors for streaming capture (C1 §6.1)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from core.audio.level import compute_peak_rms

logger = logging.getLogger(__name__)

SILERO_WINDOW_SAMPLES = 512
SILERO_SAMPLE_RATE = 16_000


@dataclass
class SegmentTracker:
    """Assemble speech frames into segments using hangover/min-speech rules."""

    min_speech_ms: int = 250
    hangover_ms: int = 500
    max_segment_ms: int = 0
    frame_ms: int = 30
    _segment_frames: list[bytes] = field(default_factory=list)
    _speech_ms: int = 0
    _silence_ms: int = 0

    def reset(self) -> None:
        self._segment_frames = []
        self._speech_ms = 0
        self._silence_ms = 0

    def feed(self, chunk: bytes, is_speech: bool) -> bytes | None:
        """Return completed segment PCM or None."""
        if is_speech:
            self._speech_ms += self.frame_ms
            self._silence_ms = 0
            self._segment_frames.append(chunk)
            if self.max_segment_ms > 0 and self._speech_ms >= self.max_segment_ms:
                return self._finalize_segment(require_min_speech=True)
            return None
        self._silence_ms += self.frame_ms
        if self._segment_frames:
            self._segment_frames.append(chunk)
        if self._segment_frames and self._silence_ms >= self.hangover_ms:
            return self._finalize_segment(require_min_speech=True)
        return None

    def flush(self, *, force: bool = False) -> bytes | None:
        if not self._segment_frames:
            return None
        if force or self._speech_ms >= self.min_speech_ms:
            return self._finalize_segment(require_min_speech=not force)
        self.reset()
        return None

    def _finalize_segment(self, *, require_min_speech: bool) -> bytes | None:
        if not self._segment_frames:
            return None
        if require_min_speech and self._speech_ms < self.min_speech_ms:
            self.reset()
            return None
        pcm = b"".join(self._segment_frames)
        self.reset()
        return pcm


class SpeechDetector(ABC):
    @abstractmethod
    def reset(self) -> None:
        ...

    @abstractmethod
    def is_speech(self, chunk: bytes) -> bool:
        ...


class EnergySpeechDetector(SpeechDetector):
    """RMS energy VAD (fallback)."""

    def __init__(self, threshold: float = 0.02) -> None:
        self._threshold = threshold

    def reset(self) -> None:
        return

    def is_speech(self, chunk: bytes) -> bool:
        _peak, rms = compute_peak_rms(chunk)
        return rms >= self._threshold


class SileroSpeechDetector(SpeechDetector):
    """Silero VAD via torch.hub (optional `pip install stt-aio[vad]`)."""

    def __init__(self, threshold: float = 0.5) -> None:
        self._threshold = threshold
        self._model = None
        self._buffer = np.array([], dtype=np.float32)
        self._load_model()

    def _load_model(self) -> None:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "Silero VAD requires torch. pip install stt-aio[vad] or use energy VAD."
            ) from exc
        self._model, _utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
            trust_repo=True,
        )
        self._model.eval()
        self._torch = torch

    def reset(self) -> None:
        self._buffer = np.array([], dtype=np.float32)

    def is_speech(self, chunk: bytes) -> bool:
        if self._model is None:
            return False
        samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return False
        self._buffer = np.concatenate([self._buffer, samples])
        speech_hits = 0
        windows = 0
        while self._buffer.size >= SILERO_WINDOW_SAMPLES:
            window = self._buffer[:SILERO_WINDOW_SAMPLES]
            self._buffer = self._buffer[SILERO_WINDOW_SAMPLES:]
            tensor = self._torch.from_numpy(window)
            with self._torch.no_grad():
                prob = float(self._model(tensor, SILERO_SAMPLE_RATE).item())
            windows += 1
            if prob >= self._threshold:
                speech_hits += 1
        if windows == 0:
            _peak, rms = compute_peak_rms(chunk)
            return rms >= 0.02
        return speech_hits >= max(1, windows // 2)


def _energy_threshold(vad_threshold: float) -> float:
    """Map UI threshold (often 0.5) to RMS scale (~0.02)."""
    if vad_threshold <= 0.15:
        return max(0.005, vad_threshold)
    return max(0.01, vad_threshold * 0.04)


def create_speech_detector(
    engine: str,
    *,
    threshold: float,
) -> SpeechDetector:
    normalized = (engine or "energy").strip().lower()
    if normalized == "silero":
        try:
            return SileroSpeechDetector(threshold=threshold)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Silero VAD unavailable (%s); using energy VAD", exc)
    return EnergySpeechDetector(threshold=_energy_threshold(threshold))
