"""Text injection facade (C5)."""

from __future__ import annotations

import logging
import sys

from core.inject.clipboard_input import paste_via_clipboard
from core.inject.errors import (
    InjectError,
    InjectionFailedError,
    NoForegroundWindowError,
    PlatformNotSupportedError,
)
from core.inject.foreground import ensure_foreground_window
from core.inject.types import (
    InjectCapabilities,
    InjectMethod,
    InjectOptions,
    InjectResult,
)
from core.inject.unicode_input import send_backspaces, send_enter, send_unicode_text

logger = logging.getLogger(__name__)


class Injector:
    """Windows text injector with unicode and clipboard strategies."""

    def __init__(
        self,
        *,
        default_method: InjectMethod = InjectMethod.AUTO,
        length_threshold: int = 500,
        press_enter: bool = False,
        unicode_fallback_to_clipboard: bool = True,
    ) -> None:
        self._default_method = default_method
        self._length_threshold = length_threshold
        self._press_enter = press_enter
        self._unicode_fallback_to_clipboard = unicode_fallback_to_clipboard

    def capabilities(self) -> InjectCapabilities:
        is_windows = sys.platform == "win32"
        return InjectCapabilities(
            supports_unicode=is_windows,
            supports_clipboard=is_windows,
            supports_replacement=is_windows,
            platform="windows" if is_windows else sys.platform,
        )

    def inject(
        self,
        text: str,
        method: InjectMethod | str | None = None,
        options: InjectOptions | None = None,
    ) -> InjectResult:
        if sys.platform != "win32":
            return InjectResult(
                success=False,
                method_used=InjectMethod.UNICODE,
                error=str(PlatformNotSupportedError("Injector requires Windows")),
            )

        opts = options or InjectOptions(
            press_enter=self._press_enter,
            length_threshold=self._length_threshold,
            unicode_fallback_to_clipboard=self._unicode_fallback_to_clipboard,
        )
        effective_method = (
            InjectMethod(method) if method is not None else self._default_method
        )
        resolved = self._resolve_method(text, effective_method, opts.length_threshold)

        if not text:
            return InjectResult(
                success=True,
                method_used=resolved,
                chars_injected=0,
            )

        try:
            if opts.target_check:
                ensure_foreground_window()
            return self._inject_with_method(text, resolved, opts)
        except NoForegroundWindowError as exc:
            self._record_inject_failure(exc, method=resolved, text_len=len(text))
            return InjectResult(
                success=False,
                method_used=resolved,
                error=str(exc),
            )
        except InjectError as exc:
            return self._handle_inject_error(text, resolved, opts, exc)

    def replace_last(
        self,
        new_text: str,
        prev_text_len: int,
        method: InjectMethod | str | None = None,
        options: InjectOptions | None = None,
    ) -> InjectResult:
        opts = options or InjectOptions(
            press_enter=self._press_enter,
            length_threshold=self._length_threshold,
            unicode_fallback_to_clipboard=self._unicode_fallback_to_clipboard,
        )
        effective_method = (
            InjectMethod(method) if method is not None else self._default_method
        )
        if not opts.allow_replacement:
            return InjectResult(
                success=False,
                method_used=self._resolve_method(
                    new_text,
                    effective_method,
                    opts.length_threshold,
                ),
                error="replacement is disabled by options.allow_replacement",
            )
        try:
            if opts.target_check:
                ensure_foreground_window()
            send_backspaces(prev_text_len)
            inner_opts = InjectOptions(
                press_enter=opts.press_enter,
                per_char_delay_ms=opts.per_char_delay_ms,
                length_threshold=opts.length_threshold,
                unicode_fallback_to_clipboard=opts.unicode_fallback_to_clipboard,
                target_check=False,
                allow_replacement=opts.allow_replacement,
            )
            return self.inject(new_text, method=effective_method, options=inner_opts)
        except InjectError as exc:
            return InjectResult(
                success=False,
                method_used=self._resolve_method(
                    new_text,
                    effective_method,
                    opts.length_threshold,
                ),
                error=str(exc),
            )

    def _handle_inject_error(
        self,
        text: str,
        resolved: InjectMethod,
        opts: InjectOptions,
        exc: InjectError,
    ) -> InjectResult:
        if (
            resolved == InjectMethod.UNICODE
            and opts.unicode_fallback_to_clipboard
            and isinstance(exc, InjectionFailedError)
        ):
            logger.warning("Unicode injection failed, falling back to clipboard")
            try:
                return self._inject_with_method(text, InjectMethod.CLIPBOARD, opts)
            except InjectError as fallback_exc:
                self._record_inject_failure(
                    fallback_exc,
                    method=InjectMethod.CLIPBOARD,
                    text_len=len(text),
                )
                return InjectResult(
                    success=False,
                    method_used=InjectMethod.CLIPBOARD,
                    error=str(fallback_exc),
                )
        self._record_inject_failure(exc, method=resolved, text_len=len(text))
        return InjectResult(
            success=False,
            method_used=resolved,
            error=str(exc),
        )

    @staticmethod
    def _record_inject_failure(
        error: BaseException | str,
        *,
        method: InjectMethod,
        text_len: int,
    ) -> None:
        from core.diagnostics import report_error

        report_error(
            error,
            context={
                "component": "injector",
                "method": method.value,
                "text_len": text_len,
            },
            log=False,
        )

    def _inject_with_method(
        self,
        text: str,
        method: InjectMethod,
        opts: InjectOptions,
    ) -> InjectResult:
        if method == InjectMethod.CLIPBOARD:
            paste_via_clipboard(text)
            chars = len(text)
        else:
            chars = send_unicode_text(
                text,
                per_char_delay_ms=opts.per_char_delay_ms,
            )
        if opts.press_enter:
            send_enter()
        return InjectResult(
            success=True,
            method_used=method,
            chars_injected=chars,
        )

    def _resolve_method(
        self,
        text: str,
        method: InjectMethod,
        length_threshold: int,
    ) -> InjectMethod:
        if method != InjectMethod.AUTO:
            return method
        if len(text) > length_threshold:
            return InjectMethod.CLIPBOARD
        return InjectMethod.UNICODE
