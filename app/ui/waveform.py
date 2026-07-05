"""Waveform rendering widget (C12)."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class WaveformWidget(QWidget):
    """Simple bar waveform rendered at capped FPS."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._samples: list[float] = []
        self._on_render_error: Callable[[str], None] | None = None
        self.setMinimumHeight(28)
        self.setMaximumHeight(28)

    def set_render_error_callback(self, callback: Callable[[str], None]) -> None:
        self._on_render_error = callback

    def set_samples(self, samples: list[float]) -> None:
        self._samples = samples
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), QColor(20, 24, 32, 220))

            if not self._samples:
                return

            width = self.width()
            height = self.height()
            bar_width = max(2, width // max(len(self._samples), 1))
            painter.setBrush(QColor(72, 196, 255))
            for index, level in enumerate(self._samples):
                bar_height = max(2, int(level * (height - 4)))
                x = index * bar_width
                y = (height - bar_height) // 2
                painter.drawRect(x, y, max(1, bar_width - 1), bar_height)
        except Exception:
            logger.exception("Waveform render failed")
            if self._on_render_error is not None:
                self._on_render_error("파형 표시 오류")
