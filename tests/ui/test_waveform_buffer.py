"""Tests for waveform buffer."""

from __future__ import annotations

from app.ui.waveform_buffer import WaveformBuffer


def test_waveform_buffer_capacity() -> None:
    buffer = WaveformBuffer(capacity=3)
    buffer.push(0.1)
    buffer.push(0.2)
    buffer.push(0.3)
    buffer.push(0.4)
    assert buffer.values() == [0.2, 0.3, 0.4]


def test_waveform_buffer_clamps_levels() -> None:
    buffer = WaveformBuffer(capacity=2)
    buffer.push(-1.0)
    buffer.push(2.0)
    assert buffer.values() == [0.0, 1.0]
