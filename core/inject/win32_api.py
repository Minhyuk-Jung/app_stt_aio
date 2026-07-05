"""Thin Win32 API wrapper (mockable in tests)."""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

from core.inject.errors import PlatformNotSupportedError

if sys.platform == "win32":
    ULONG_PTR = (
        ctypes.c_ulonglong
        if ctypes.sizeof(ctypes.c_void_p) == 8
        else ctypes.c_ulong
    )

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.c_void_p

    INPUT_KEYBOARD = 1
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    VK_BACK = 0x08
    VK_RETURN = 0x0D
    VK_CONTROL = 0x11
    VK_A = 0x41
    VK_C = 0x43
    VK_V = 0x56


def ensure_windows() -> None:
    if sys.platform != "win32":
        raise PlatformNotSupportedError("Injector requires Windows")


def get_foreground_window() -> int:
    ensure_windows()
    return int(user32.GetForegroundWindow())


def send_input(events: list) -> int:
    ensure_windows()
    if not events:
        return 0
    array_type = INPUT * len(events)
    sent = user32.SendInput(len(events), array_type(*events), ctypes.sizeof(INPUT))
    return int(sent)


def sleep_ms(delay_ms: int) -> None:
    if delay_ms > 0:
        time.sleep(delay_ms / 1000)


def open_clipboard() -> bool:
    ensure_windows()
    return bool(user32.OpenClipboard(None))


def close_clipboard() -> bool:
    ensure_windows()
    return bool(user32.CloseClipboard())


def empty_clipboard() -> bool:
    ensure_windows()
    return bool(user32.EmptyClipboard())


def get_clipboard_text() -> str | None:
    ensure_windows()
    handle = user32.GetClipboardData(CF_UNICODETEXT)
    if not handle:
        return None
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        return None
    try:
        return ctypes.wstring_at(pointer)
    finally:
        kernel32.GlobalUnlock(handle)


def set_clipboard_text(text: str) -> bool:
    ensure_windows()
    encoded = (text + "\x00").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    if not handle:
        return False
    locked = kernel32.GlobalLock(handle)
    if not locked:
        kernel32.GlobalFree(handle)
        return False
    try:
        ctypes.memmove(locked, encoded, len(encoded))
    finally:
        kernel32.GlobalUnlock(handle)
    if not user32.SetClipboardData(CF_UNICODETEXT, handle):
        kernel32.GlobalFree(handle)
        return False
    return True
