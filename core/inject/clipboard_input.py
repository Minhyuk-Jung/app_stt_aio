"""Clipboard backup, paste, and restore."""

from __future__ import annotations

import logging
import time

from core.inject.errors import ClipboardBusyError, InjectionFailedError
from core.inject.win32_api import (
    INPUT,
    INPUT_KEYBOARD,
    INPUT_UNION,
    KEYBDINPUT,
    KEYEVENTF_KEYUP,
    ULONG_PTR,
    VK_CONTROL,
    VK_V,
    close_clipboard,
    empty_clipboard,
    get_clipboard_text,
    open_clipboard,
    send_input,
    set_clipboard_text,
)

logger = logging.getLogger(__name__)

_CLIPBOARD_RETRY_ATTEMPTS = 3
_CLIPBOARD_RETRY_DELAY_SEC = 0.05
_RESTORE_DELAY_SEC = 0.05


def _send_ctrl_v() -> None:
    events = [
        _vk_event(VK_CONTROL, key_up=False),
        _vk_event(VK_V, key_up=False),
        _vk_event(VK_V, key_up=True),
        _vk_event(VK_CONTROL, key_up=True),
    ]
    sent = send_input(events)
    if sent != len(events):
        raise InjectionFailedError("failed to send Ctrl+V sequence")


def _vk_event(vk_code: int, *, key_up: bool) -> INPUT:
    event = INPUT()
    event.type = INPUT_KEYBOARD
    flags = KEYEVENTF_KEYUP if key_up else 0
    event.union = INPUT_UNION(
        ki=KEYBDINPUT(vk_code, 0, flags, 0, ULONG_PTR(0))
    )
    return event


def _with_clipboard():
    last_error: Exception | None = None
    for attempt in range(_CLIPBOARD_RETRY_ATTEMPTS):
        if open_clipboard():
            return
        last_error = ClipboardBusyError("clipboard is busy")
        time.sleep(_CLIPBOARD_RETRY_DELAY_SEC * (attempt + 1))
    raise last_error or ClipboardBusyError("clipboard is busy")


def paste_via_clipboard(text: str) -> None:
    backup = _read_clipboard_backup()
    _with_clipboard()
    try:
        if not empty_clipboard():
            raise InjectionFailedError("failed to empty clipboard")
        if not set_clipboard_text(text):
            raise InjectionFailedError("failed to set clipboard text")
    finally:
        close_clipboard()

    _send_ctrl_v()
    time.sleep(_RESTORE_DELAY_SEC)
    _restore_clipboard(backup)


def _read_clipboard_backup() -> str | None:
    try:
        _with_clipboard()
    except ClipboardBusyError:
        logger.warning("Could not back up clipboard before paste")
        return None
    try:
        return get_clipboard_text()
    finally:
        close_clipboard()


def verify_clipboard_roundtrip(text: str) -> bool:
    """Set/get clipboard UTF-16 text; restore prior clipboard contents."""
    backup = _read_clipboard_backup()
    try:
        _with_clipboard()
        try:
            if not empty_clipboard():
                return False
            if not set_clipboard_text(text):
                return False
        finally:
            close_clipboard()
        _with_clipboard()
        try:
            recovered = get_clipboard_text()
        finally:
            close_clipboard()
        return recovered == text
    finally:
        _restore_clipboard(backup)


def _restore_clipboard(original: str | None) -> None:
    for attempt in range(_CLIPBOARD_RETRY_ATTEMPTS):
        try:
            _with_clipboard()
        except ClipboardBusyError as exc:
            if attempt + 1 == _CLIPBOARD_RETRY_ATTEMPTS:
                logger.warning("Could not restore clipboard: %s", exc)
                return
            time.sleep(_CLIPBOARD_RETRY_DELAY_SEC * (attempt + 1))
            continue
        try:
            if not empty_clipboard():
                if attempt + 1 == _CLIPBOARD_RETRY_ATTEMPTS:
                    logger.warning("Could not empty clipboard during restore")
                else:
                    close_clipboard()
                    time.sleep(_CLIPBOARD_RETRY_DELAY_SEC * (attempt + 1))
                    continue
                return
            if original is not None and not set_clipboard_text(original):
                logger.warning("Could not restore previous clipboard contents")
            return
        finally:
            close_clipboard()
