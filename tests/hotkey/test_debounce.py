"""Tests for key debounce."""

from __future__ import annotations

from unittest.mock import patch

from app.hotkey.debounce import KeyDebouncer


def test_debouncer_accepts_first_down() -> None:
    debouncer = KeyDebouncer(interval_ms=50)
    assert debouncer.accept("space", is_repeat=False) is True


def test_debouncer_rejects_fast_repeats() -> None:
    clock = {"t": 1000.0}

    def monotonic() -> float:
        return clock["t"]

    with patch("app.hotkey.debounce.time.monotonic", side_effect=monotonic):
        debouncer = KeyDebouncer(interval_ms=100)
        assert debouncer.accept("space", is_repeat=False) is True
        clock["t"] += 0.01
        assert debouncer.accept("space", is_repeat=True) is False


def test_debouncer_accepts_repeat_after_interval() -> None:
    clock = {"t": 2000.0}

    def monotonic() -> float:
        return clock["t"]

    with patch("app.hotkey.debounce.time.monotonic", side_effect=monotonic):
        debouncer = KeyDebouncer(interval_ms=20)
        assert debouncer.accept("space", is_repeat=False) is True
        clock["t"] += 0.03
        assert debouncer.accept("space", is_repeat=True) is True
