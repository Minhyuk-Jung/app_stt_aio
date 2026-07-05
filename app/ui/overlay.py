"""Frameless overlay bar (C12)."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.ui.state_view import OverlayDisplayState, overlay_status_text
from app.ui.waveform import WaveformWidget


class OverlayWindow(QWidget):
    """Always-on-top overlay showing dictation status and waveform."""

    REFRESH_MS = 33  # ~30fps cap per plan
    ERROR_DISMISS_MS = 3000

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.92)
        self.setStyleSheet(
            "OverlayWindow {"
            "  background-color: rgba(20, 24, 32, 210);"
            "  border-radius: 10px;"
            "}"
        )
        self._drag_offset: QPoint | None = None
        self._on_error_dismissed: Callable[[], None] | None = None
        self._on_render_error: Callable[[str], None] | None = None

        self._status_label = QLabel("대기")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self._status_label.setFont(font)
        self._status_label.setStyleSheet("color: white;")

        self._waveform = WaveformWidget()
        self._waveform.hide()

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self._status_label)
        layout.addWidget(self._waveform)
        self.setLayout(layout)
        self.resize(280, 72)
        self._place_bottom_center()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self.REFRESH_MS)
        self._refresh_timer.timeout.connect(self._on_refresh_tick)
        self._pending_samples: list[float] | None = None
        self._display_state = OverlayDisplayState.IDLE

        self._recording_started_at: float | None = None
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(200)
        self._elapsed_timer.timeout.connect(self._update_recording_elapsed)

        self._processing_timer = QTimer(self)
        self._processing_timer.setInterval(400)
        self._processing_timer.timeout.connect(self._animate_processing_label)
        self._processing_dots = 0
        self._processing_stage: int | None = None

        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(self._dismiss_error_display)

    def set_error_dismiss_callback(self, callback: Callable[[], None]) -> None:
        self._on_error_dismissed = callback

    def set_render_error_callback(self, callback: Callable[[str], None]) -> None:
        self._on_render_error = callback
        self._waveform.set_render_error_callback(self.notify_render_error)

    def set_display_state(
        self,
        state: OverlayDisplayState,
        _label: str = "",
        *,
        processing_stage: int | None = None,
    ) -> None:
        self._display_state = state
        self._processing_stage = processing_stage
        self._elapsed_timer.stop()
        self._processing_timer.stop()
        self._error_timer.stop()

        if state is OverlayDisplayState.HIDDEN:
            self.hide()
            self._refresh_timer.stop()
            self._waveform.hide()
            return

        self.show()
        if state is OverlayDisplayState.RECORDING:
            self._recording_started_at = time.monotonic()
            self._status_label.setText(_label or overlay_status_text(state))
            self._waveform.show()
            self._elapsed_timer.start()
            if not self._refresh_timer.isActive():
                self._refresh_timer.start()
            return

        self._waveform.hide()
        self._refresh_timer.stop()
        self._waveform.set_samples([])

        if state is OverlayDisplayState.PROCESSING:
            self._processing_dots = 0
            self._processing_timer.start()
            self._update_processing_label()
            return

        if state is OverlayDisplayState.ERROR:
            self._status_label.setText(_label or overlay_status_text(state))
            self._error_timer.start(self.ERROR_DISMISS_MS)
            return

        self._status_label.setText(_label or overlay_status_text(state))

    def queue_waveform(self, samples: list[float]) -> None:
        self._pending_samples = samples

    def _on_refresh_tick(self) -> None:
        if self._pending_samples is not None:
            self._waveform.set_samples(self._pending_samples)

    def _update_recording_elapsed(self) -> None:
        if self._recording_started_at is None:
            return
        elapsed = int(time.monotonic() - self._recording_started_at)
        minutes, seconds = divmod(elapsed, 60)
        self._status_label.setText(f"녹음 중 {minutes}:{seconds:02d}")

    def _animate_processing_label(self) -> None:
        self._processing_dots = (self._processing_dots + 1) % 4
        dots = "." * self._processing_dots
        from app.ui.state_view import overlay_status_text

        base = overlay_status_text(
            OverlayDisplayState.PROCESSING,
            processing_stage=self._processing_stage,
        )
        self._status_label.setText(f"{base}{dots}")

    def _update_processing_label(self) -> None:
        from app.ui.state_view import overlay_status_text

        self._status_label.setText(
            overlay_status_text(
                OverlayDisplayState.PROCESSING,
                processing_stage=self._processing_stage,
            )
        )

    def _dismiss_error_display(self) -> None:
        if self._display_state is not OverlayDisplayState.ERROR:
            return
        if self._on_error_dismissed is not None:
            self._on_error_dismissed()

    def notify_render_error(self, message: str) -> None:
        if self._on_render_error is not None:
            self._on_render_error(message)

    def _place_bottom_center(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        x = geometry.x() + (geometry.width() - self.width()) // 2
        y = geometry.y() + geometry.height() - self.height() - 48
        self.move(x, y)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)
