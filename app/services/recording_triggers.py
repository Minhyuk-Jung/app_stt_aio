"""P1 glue: HotkeyManager events drive AudioCapture batch recording (pre-C10)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.audio.format import AudioBuffer

if TYPE_CHECKING:
    from app.hotkey.hotkey_manager import HotkeyManager
    from core.audio.audio_capture import AudioCapture

BatchStoppedCallback = Callable[[AudioBuffer], None]


def wire_hotkey_to_audio_capture(
    hotkey: HotkeyManager,
    capture: AudioCapture,
    *,
    on_batch_stopped: BatchStoppedCallback | None = None,
) -> None:
    """Connect C9 record/cancel events to C1 batch capture (P1 MVP path)."""
    active_handle = None

    def on_record_start() -> None:
        nonlocal active_handle
        active_handle = capture.start_batch()

    def on_record_stop() -> None:
        nonlocal active_handle
        if active_handle is None:
            return
        audio = capture.stop_batch(active_handle)
        active_handle = None
        if on_batch_stopped is not None:
            on_batch_stopped(audio)

    def on_cancel() -> None:
        nonlocal active_handle
        if active_handle is None:
            return
        capture.cancel(active_handle)
        active_handle = None

    hotkey.on_record_start(on_record_start)
    hotkey.on_record_stop(on_record_stop)
    hotkey.on_cancel(on_cancel)
