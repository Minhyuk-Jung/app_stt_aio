"""Thread-safe Qt signal dispatcher for UI updates (C12)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.ui.state_view import OverlayDisplayState


class QtUiDispatcher(QObject):
    """Marshal background session events onto the Qt main thread."""

    display_state_changed = Signal(OverlayDisplayState, str)
    waveform_changed = Signal(list)
    error_notice = Signal(str, str)
    inject_feedback = Signal(str, bool)
    workbench_refresh = Signal(str)
    workbench_stage_completed = Signal(str, int)
