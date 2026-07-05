"""Hotkey domain types (C9)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

HotkeyCallback = Callable[[], None]
ConflictCallback = Callable[["HotkeyBinding"], None]


class HotkeyAction(str, Enum):
    RECORD = "record"
    CANCEL = "cancel"
    AUTO_SEND = "auto_send"


class HotkeyMode(str, Enum):
    PTT = "ptt"
    TOGGLE = "toggle"


class RecordTriggerState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"


@dataclass(frozen=True)
class HotkeyBinding:
    id: str
    keys: str
    action: HotkeyAction
    mode: HotkeyMode | None = None
