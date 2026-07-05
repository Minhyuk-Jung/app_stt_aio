"""Download cancellation and byte progress (C18)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class DownloadController:
    """Thread-safe cancel token for model downloads."""

    _event: threading.Event = field(default_factory=threading.Event)
    downloaded_bytes: int = 0
    total_bytes: int = 0

    @property
    def canceled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def update_progress(self, downloaded: int, total: int) -> None:
        self.downloaded_bytes = max(0, downloaded)
        self.total_bytes = max(0, total)

    def raise_if_canceled(self) -> None:
        if self.canceled:
            from core.models.errors import ModelDownloadError

            raise ModelDownloadError("다운로드가 사용자에 의해 취소되었습니다.")
