"""Tests for C1 AudioCapture (P1 batch + format/resample)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.audio import (
    AudioBuffer,
    AudioCapture,
    AudioSettings,
    CaptureBusyError,
    CaptureState,
    MaxDurationExceededError,
)
from core.audio.capture_batch import generate_test_tone
from core.audio.level import compute_peak_rms
from core.audio.resample import build_audio_buffer, to_standard_pcm


def test_audio_buffer_duration() -> None:
    pcm = generate_test_tone(duration_ms=1000, sample_rate=16000)
    buffer = AudioBuffer(pcm_bytes=pcm)
    assert buffer.duration_ms == 1000


def test_to_standard_pcm_mono_resample() -> None:
    source = generate_test_tone(duration_ms=1000, sample_rate=48000, channels=1)
    converted = to_standard_pcm(source, sample_rate=48000, channels=1)
    buffer = build_audio_buffer(source, sample_rate=48000, channels=1)
    assert buffer.sample_rate == 16000
    assert buffer.channels == 1
    assert buffer.sample_width == 2
    assert abs(buffer.duration_ms - 1000) <= 2
    assert len(converted) == len(buffer.pcm_bytes)


def test_to_standard_pcm_stereo_downmix() -> None:
    left = generate_test_tone(duration_ms=500, sample_rate=16000, channels=1)
    right = generate_test_tone(frequency_hz=880.0, duration_ms=500, sample_rate=16000, channels=1)
    stereo = np.column_stack(
        [np.frombuffer(left, dtype=np.int16), np.frombuffer(right, dtype=np.int16)]
    ).reshape(-1)
    buffer = build_audio_buffer(stereo.tobytes(), sample_rate=16000, channels=2)
    assert buffer.channels == 1
    assert buffer.duration_ms == 500


class _FakeStream:
    def __init__(self, callback, **kwargs) -> None:  # noqa: ANN003
        self.callback = callback
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True

    def push(self, frames: int = 480) -> None:
        chunk = np.zeros((frames, self.kwargs["channels"]), dtype=np.int16)
        self.callback(chunk, frames, None, None)


@patch("core.audio.capture_batch.sd.query_devices")
@patch("core.audio.capture_batch.sd.InputStream", _FakeStream)
def test_batch_capture_start_stop(mock_batch_device_query) -> None:
    device_info = {
        "name": "Mic",
        "hostapi": 0,
        "max_input_channels": 1,
        "default_samplerate": 48000.0,
    }
    mock_batch_device_query.return_value = device_info

    capture = AudioCapture()
    handle = capture.start_batch()
    assert capture.state == CaptureState.RECORDING

    recording = capture._batch._active
    assert recording is not None
    recording._stream.push()
    recording._stream.push()

    buffer = capture.stop_batch(handle)
    assert capture.state == CaptureState.IDLE
    assert isinstance(buffer, AudioBuffer)
    assert buffer.sample_rate == 16000
    assert buffer.channels == 1
    assert buffer.duration_ms > 0


@patch("core.audio.capture_batch.sd.query_devices")
@patch("core.audio.capture_batch.sd.InputStream", _FakeStream)
@patch("core.audio.device.sd.query_devices")
def test_batch_capture_cancel(mock_device_query, mock_batch_device_query) -> None:
    device_info = {
        "name": "Mic",
        "hostapi": 0,
        "max_input_channels": 1,
        "default_samplerate": 48000.0,
    }
    mock_device_query.return_value = [device_info]
    mock_batch_device_query.return_value = device_info

    capture = AudioCapture()
    handle = capture.start_batch()
    capture.cancel(handle)
    assert capture.state == CaptureState.IDLE


@patch("core.audio.capture_batch.sd.query_devices")
@patch("core.audio.capture_batch.sd.InputStream", _FakeStream)
@patch("core.audio.device.sd.query_devices")
def test_batch_capture_rejects_parallel_start(mock_device_query, mock_batch_device_query) -> None:
    device_info = {
        "name": "Mic",
        "hostapi": 0,
        "max_input_channels": 1,
        "default_samplerate": 48000.0,
    }
    mock_device_query.return_value = [device_info]
    mock_batch_device_query.return_value = device_info

    capture = AudioCapture()
    handle = capture.start_batch()
    with pytest.raises(CaptureBusyError):
        capture.start_batch()
    capture.cancel(handle)


def test_start_stream_enters_streaming_state() -> None:
    from unittest.mock import MagicMock, patch

    capture = AudioCapture()
    mock_handle = MagicMock()
    with patch("core.audio.stream_capture.StreamCapture") as mock_stream_cls:
        mock_stream_cls.return_value.start.return_value = mock_handle
        handle = capture.start_stream(lambda *_: None)
    assert handle is mock_handle
    assert capture.state == CaptureState.STREAMING
    capture.stop_stream(mock_handle)
    assert capture.state == CaptureState.IDLE


def test_apply_settings() -> None:
    capture = AudioCapture()
    capture.apply_settings(AudioSettings(device_id="", max_segment_ms=15000))
    assert capture._max_batch_duration_ms == 15000


def test_reset_from_error_state() -> None:
    capture = AudioCapture()
    capture._state = CaptureState.ERROR
    capture.reset()
    assert capture.state == CaptureState.IDLE
    assert capture._batch.is_active is False


def test_reset_cleans_active_recording() -> None:
    from core.audio.capture_batch import BatchRecording

    capture = AudioCapture()
    recording = BatchRecording(
        handle_id=1,
        device_id=None,
        stream_channels=1,
        sample_rate=16000,
    )
    capture._batch._active = recording
    capture._state = CaptureState.ERROR
    capture.reset()
    assert capture.state == CaptureState.IDLE
    assert capture._batch.is_active is False


@patch("core.audio.capture_batch.sd.query_devices")
@patch("core.audio.capture_batch.sd.InputStream", _FakeStream)
def test_stop_batch_recovers_partial_audio_from_error(mock_batch_device_query) -> None:
    device_info = {
        "name": "Mic",
        "hostapi": 0,
        "max_input_channels": 1,
        "default_samplerate": 48000.0,
    }
    mock_batch_device_query.return_value = device_info

    capture = AudioCapture()
    handle = capture.start_batch()
    recording = capture._batch._active
    assert recording is not None
    recording._stream.push()
    capture._state = CaptureState.ERROR

    buffer = capture.stop_batch(handle)
    assert capture.state == CaptureState.IDLE
    assert not buffer.is_empty


def test_audio_buffer_is_empty() -> None:
    assert AudioBuffer(pcm_bytes=b"").is_empty
    assert not AudioBuffer(pcm_bytes=generate_test_tone(duration_ms=10)).is_empty


def test_compute_peak_rms() -> None:
    pcm = generate_test_tone(duration_ms=100, sample_rate=16000)
    peak, rms = compute_peak_rms(pcm)
    assert 0.0 < peak <= 1.0
    assert 0.0 < rms <= 1.0


def test_batch_max_duration_exceeded() -> None:
    from core.audio.capture_batch import BatchCapture, BatchRecording

    recording = BatchRecording(
        handle_id=1,
        device_id=None,
        stream_channels=1,
        sample_rate=48000,
        max_duration_ms=50,
    )
    chunk = generate_test_tone(duration_ms=10, sample_rate=48000, channels=1)

    errors: list[Exception] = []
    batch = BatchCapture(on_error=lambda e: errors.append(e))
    batch._emit_error = lambda e: errors.append(e)  # noqa: SLF001

    for _ in range(20):
        recording.append_chunk(chunk)
        if recording.duration_exceeded:
            batch._emit_error(  # noqa: SLF001
                MaxDurationExceededError("batch recording exceeded 50ms limit")
            )
            break

    assert recording.duration_exceeded
    assert any(isinstance(err, MaxDurationExceededError) for err in errors)
    assert recording._current_duration_ms() <= 70
