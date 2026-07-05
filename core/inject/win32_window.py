"""Win32 window helpers for injection smoke tests (C5)."""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from ctypes import wintypes

from core.inject.errors import PlatformNotSupportedError
from core.inject.win32_api import (
    INPUT,
    INPUT_KEYBOARD,
    INPUT_UNION,
    KEYBDINPUT,
    KEYEVENTF_KEYUP,
    ULONG_PTR,
    VK_A,
    VK_BACK,
    VK_C,
    VK_CONTROL,
    ensure_windows,
    get_clipboard_text,
    get_foreground_window,
    open_clipboard,
    close_clipboard,
    send_input,
    set_clipboard_text,
    empty_clipboard,
)

if sys.platform == "win32":
    user32 = ctypes.windll.user32
    WM_GETTEXT = 0x000D
    WM_GETTEXTLENGTH = 0x000E
    SW_RESTORE = 9


def find_notepad_window(*, timeout_sec: float = 8.0) -> int:
    """Locate Notepad top-level HWND (classic class or localized title)."""
    ensure_windows()
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        hwnd = int(user32.FindWindowW("Notepad", None))
        if hwnd:
            return hwnd
        for needle in ("메모장", "Notepad"):
            hwnd = find_top_level_window(title_contains=needle, timeout_sec=0.2)
            if hwnd:
                return hwnd
        time.sleep(0.15)
    return 0


def focus_window(hwnd: int) -> bool:
    ensure_windows()
    if hwnd == 0:
        return False
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.BringWindowToTop(hwnd)
    foreground = int(user32.GetForegroundWindow())
    fg_thread = user32.GetWindowThreadProcessId(foreground, None)
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    attached = False
    if fg_thread and target_thread and fg_thread != target_thread:
        attached = bool(user32.AttachThreadInput(fg_thread, target_thread, True))
    try:
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(fg_thread, target_thread, False)
    time.sleep(0.15)
    if int(user32.GetForegroundWindow()) == hwnd:
        return True
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(New-Object -ComObject WScript.Shell).AppActivate({hwnd})",
            ],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    time.sleep(0.2)
    return int(user32.GetForegroundWindow()) == hwnd


def set_foreground_window(hwnd: int) -> bool:
    return focus_window(hwnd)


def find_top_level_window(*, title_contains: str, timeout_sec: float = 5.0) -> int:
    """Return HWND of first top-level window whose title contains *title_contains*."""
    ensure_windows()
    deadline = time.monotonic() + timeout_sec
    needle = title_contains.casefold()

    while time.monotonic() < deadline:
        matches: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            buff = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buff, 512)
            if needle in buff.value.casefold():
                matches.append(int(hwnd))
            return True

        user32.EnumWindows(_enum, 0)
        if matches:
            return matches[0]
        time.sleep(0.1)
    return 0


def find_child_by_class(parent_hwnd: int, class_name: str) -> int:
    ensure_windows()
    found: list[int] = []
    target = class_name.casefold()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd: int, _lparam: int) -> bool:
        buff = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buff, 256)
        if buff.value.casefold() == target:
            found.append(int(hwnd))
            return False
        return True

    user32.EnumChildWindows(parent_hwnd, _enum, 0)
    return found[0] if found else 0


def get_window_text(hwnd: int) -> str:
    ensure_windows()
    length = int(user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0))
    if length <= 0:
        return ""
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.SendMessageW(hwnd, WM_GETTEXT, length + 1, buff)
    return buff.value


def _vk_event(vk_code: int, *, key_up: bool) -> INPUT:
    event = INPUT()
    event.type = INPUT_KEYBOARD
    flags = KEYEVENTF_KEYUP if key_up else 0
    event.union = INPUT_UNION(
        ki=KEYBDINPUT(vk_code, 0, flags, 0, ULONG_PTR(0))
    )
    return event


def _send_ctrl_key(vk: int) -> None:
    events = [
        _vk_event(VK_CONTROL, key_up=False),
        _vk_event(vk, key_up=False),
        _vk_event(vk, key_up=True),
        _vk_event(VK_CONTROL, key_up=True),
    ]
    send_input(events)
    time.sleep(0.05)


def read_focused_text_via_clipboard() -> str | None:
    """Select-all + copy from foreground window; restore prior clipboard."""
    ensure_windows()
    backup: str | None = None
    if open_clipboard():
        try:
            backup = get_clipboard_text()
        finally:
            close_clipboard()

    _send_ctrl_key(VK_A)
    _send_ctrl_key(VK_C)
    time.sleep(0.05)

    copied: str | None = None
    if open_clipboard():
        try:
            copied = get_clipboard_text()
        finally:
            close_clipboard()

    if open_clipboard():
        try:
            empty_clipboard()
            if backup is not None:
                set_clipboard_text(backup)
        finally:
            close_clipboard()
    return copied


def clear_focused_text() -> None:
    _send_ctrl_key(VK_A)
    events = [
        _vk_event(VK_BACK, key_up=False),
        _vk_event(VK_BACK, key_up=True),
    ]
    send_input(events)
    time.sleep(0.05)


def read_notepad_text(notepad_hwnd: int) -> str:
    """Read text from classic Notepad Edit control, else clipboard fallback."""
    edit_hwnd = find_child_by_class(notepad_hwnd, "Edit")
    if edit_hwnd:
        text = get_window_text(edit_hwnd)
        if text:
            return text
    if set_foreground_window(notepad_hwnd):
        time.sleep(0.1)
        copied = read_focused_text_via_clipboard()
        if copied is not None:
            return copied
    return ""
