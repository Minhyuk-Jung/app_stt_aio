"""SendInput UNICODE dispatch tests (C5, P0)."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def test_send_unicode_text_dispatches_all_code_units() -> None:
    from core.inject.text_encoding import text_to_utf16_units
    from core.inject.unicode_input import send_unicode_text

    text = "안녕 A"
    units = text_to_utf16_units(text)
    captured: list[int] = []

    def _fake_send(events: list) -> int:
        for event in events:
            if event.union.ki.dwFlags & 0x0004:  # KEYEVENTF_UNICODE
                if not (event.union.ki.dwFlags & 0x0002):  # key up only down
                    captured.append(int(event.union.ki.wScan))
        return len(events)

    with patch("core.inject.unicode_input.send_input", side_effect=_fake_send):
        count = send_unicode_text(text)

    assert count == len(text)
    assert captured == units


def test_injector_unicode_reports_chars_injected() -> None:
    from core.inject.injector import Injector
    from core.inject.types import InjectMethod, InjectOptions

    sample = "안녕하세요"
    injector = Injector(default_method=InjectMethod.UNICODE)

    with patch("core.inject.injector.send_unicode_text", return_value=len(sample)) as mock_send:
        result = injector.inject(
            sample,
            method=InjectMethod.UNICODE,
            options=InjectOptions(target_check=False),
        )

    assert result.success
    assert result.chars_injected == len(sample)
    mock_send.assert_called_once()
