"""Realtime partial injection helper (C5 P2)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from core.inject.injector import Injector
from core.inject.types import InjectMethod, InjectOptions, InjectResult

logger = logging.getLogger(__name__)


@dataclass
class RealtimeInjector:
    """Tracks last injected text and supports replace_last for streaming STT."""

    injector: Injector
    options: InjectOptions = field(default_factory=InjectOptions)
    _last_text: str = ""

    def inject_partial(self, text: str, *, is_final: bool) -> InjectResult:
        delta = text[len(self._last_text) :] if text.startswith(self._last_text) else text
        if not delta and not is_final:
            return InjectResult(success=True, method_used=InjectMethod.UNICODE, chars_injected=0)
        if text.startswith(self._last_text) and self._last_text:
            result = self.injector.replace_last(self._last_text, text, options=self.options)
        else:
            result = self.injector.inject(text, options=self.options)
        if result.success:
            self._last_text = text if not is_final else ""
        return result

    def reset(self) -> None:
        self._last_text = ""
