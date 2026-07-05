"""Windows low-level keyboard hook backend (C9)."""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from ctypes import wintypes

from app.hotkey.backend import KeyEvent, KeyEventHandler
from app.hotkey.binding import KeyChord
from app.hotkey.errors import PlatformNotSupportedError

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    ULONG_PTR = (
        ctypes.c_ulonglong
        if ctypes.sizeof(ctypes.c_void_p) == 8
        else ctypes.c_ulong
    )

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_int,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    WH_KEYBOARD_LL = 13
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    WM_SYSKEYDOWN = 0x0104
    WM_SYSKEYUP = 0x0105
    HC_ACTION = 0
    LLKHF_REPEAT = 0x4000
    WM_QUIT = 0x0012
    PM_REMOVE = 0x0001


def test_register_hotkey(chord: KeyChord) -> bool:
    """Probe RegisterHotKey to detect OS-level conflicts."""
    if sys.platform != "win32":
        return True

    hotkey_id = 0xA10
    modifiers = _win_modifier_flags(chord.modifiers)
    registered = bool(
        user32.RegisterHotKey(None, hotkey_id, modifiers, chord.vk)
    )
    if registered:
        user32.UnregisterHotKey(None, hotkey_id)
    return registered


def _win_modifier_flags(modifiers: frozenset[str]) -> int:
    flags = 0
    if "alt" in modifiers:
        flags |= 0x0001
    if "ctrl" in modifiers:
        flags |= 0x0002
    if "shift" in modifiers:
        flags |= 0x0004
    if "win" in modifiers:
        flags |= 0x0008
    return flags


class WinKeyboardBackend:
    """Capture global key events via WH_KEYBOARD_LL."""

    def __init__(self) -> None:
        self._handler: KeyEventHandler | None = None
        self._thread: threading.Thread | None = None
        self._hook_handle = None
        self._proc_ref = None
        self._thread_id: int | None = None
        self._running = False
        self._ready = threading.Event()
        self._hook_failed = False

    @property
    def hook_failed(self) -> bool:
        return self._hook_failed

    def wait_ready(self, timeout: float = 1.0) -> bool:
        return self._ready.wait(timeout)

    def start(self, handler: KeyEventHandler) -> None:
        if sys.platform != "win32":
            raise PlatformNotSupportedError("WinKeyboardBackend requires Windows")
        if self._running:
            return

        self._handler = handler
        self._running = True
        self._hook_failed = False
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run_message_loop,
            name="hotkey-keyboard-hook",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._thread_id = None
        self._handler = None
        self._hook_handle = None
        self._proc_ref = None

    def test_register(self, chord: KeyChord) -> bool:
        return test_register_hotkey(chord)

    def _run_message_loop(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()

        @LowLevelKeyboardProc
        def hook_proc(n_code: int, w_param: int, l_param: int) -> int:
            if n_code == HC_ACTION and self._handler is not None:
                event = self._to_key_event(w_param, l_param)
                if event is not None:
                    try:
                        self._handler(event)
                    except Exception:
                        logger.exception("Hotkey handler failed")
            return user32.CallNextHookEx(self._hook_handle, n_code, w_param, l_param)

        self._proc_ref = hook_proc
        self._hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._proc_ref,
            kernel32.GetModuleHandleW(None),
            0,
        )
        if not self._hook_handle:
            logger.error("SetWindowsHookExW failed")
            self._hook_failed = True
            self._running = False
            self._ready.set()
            return

        self._ready.set()
        message = wintypes.MSG()
        while self._running:
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result == 0 or result == -1:
                break
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

        if self._hook_handle:
            user32.UnhookWindowsHookEx(self._hook_handle)

    @staticmethod
    def _to_key_event(w_param: int, l_param: int) -> KeyEvent | None:
        if w_param not in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
            return None

        struct = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        is_down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
        is_repeat = bool(struct.flags & LLKHF_REPEAT) if is_down else False
        return KeyEvent(vk=int(struct.vkCode), is_down=is_down, is_repeat=is_repeat)
