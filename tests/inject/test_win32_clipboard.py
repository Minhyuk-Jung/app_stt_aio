"""Win32 clipboard API regression (C5)."""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def test_verify_clipboard_roundtrip_korean() -> None:
    from core.inject.clipboard_input import verify_clipboard_roundtrip

    assert verify_clipboard_roundtrip("안녕하세요 STT-AIO")
    assert verify_clipboard_roundtrip("Mixed 한글English 🎤")


def test_set_clipboard_text_requires_open_clipboard() -> None:
    from core.inject.win32_api import (
        close_clipboard,
        empty_clipboard,
        get_clipboard_text,
        open_clipboard,
        set_clipboard_text,
    )

    assert open_clipboard()
    try:
        assert empty_clipboard()
        assert set_clipboard_text("probe")
    finally:
        close_clipboard()
    assert open_clipboard()
    try:
        assert get_clipboard_text() == "probe"
    finally:
        close_clipboard()
        open_clipboard()
        try:
            empty_clipboard()
        finally:
            close_clipboard()
