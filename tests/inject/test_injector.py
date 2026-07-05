"""Tests for C5 Injector (P1 batch injection)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.inject import (
    ClipboardBusyError,
    InjectMethod,
    InjectOptions,
    Injector,
    InjectionFailedError,
    NoForegroundWindowError,
)
from core.inject.text_encoding import surrogate_pair_count, text_to_utf16_units


def test_text_to_utf16_units_basic() -> None:
    assert text_to_utf16_units("안녕") == [50504, 45397]


def test_text_to_utf16_units_surrogate_pair() -> None:
    emoji = "😀"
    units = text_to_utf16_units(emoji)
    assert len(units) == 2
    assert surrogate_pair_count(emoji) == 1


def test_resolve_method_auto_short_text() -> None:
    injector = Injector(length_threshold=10)
    assert injector._resolve_method("짧은", InjectMethod.AUTO, 10) == InjectMethod.UNICODE


def test_resolve_method_auto_long_text() -> None:
    injector = Injector(length_threshold=5)
    assert injector._resolve_method("123456", InjectMethod.AUTO, 5) == InjectMethod.CLIPBOARD


def test_inject_empty_text() -> None:
    injector = Injector()
    result = injector.inject("")
    assert result.success is True
    assert result.chars_injected == 0


@patch("core.inject.injector.ensure_foreground_window", return_value=1)
@patch("core.inject.injector.send_unicode_text", return_value=3)
def test_inject_unicode(mock_send, _mock_fg) -> None:
    injector = Injector()
    result = injector.inject("안녕하", method=InjectMethod.UNICODE)
    assert result.success is True
    assert result.method_used == InjectMethod.UNICODE
    assert result.chars_injected == 3
    mock_send.assert_called_once()


@patch("core.inject.injector.ensure_foreground_window", return_value=1)
@patch("core.inject.injector.paste_via_clipboard")
def test_inject_clipboard(mock_paste, _mock_fg) -> None:
    injector = Injector()
    result = injector.inject("긴 텍스트", method=InjectMethod.CLIPBOARD)
    assert result.success is True
    assert result.method_used == InjectMethod.CLIPBOARD
    mock_paste.assert_called_once_with("긴 텍스트")


@patch("core.inject.injector.ensure_foreground_window", side_effect=NoForegroundWindowError("none"))
def test_inject_no_foreground_window(_mock_fg) -> None:
    injector = Injector()
    result = injector.inject("테스트", method=InjectMethod.UNICODE)
    assert result.success is False
    assert "none" in (result.error or "")


@patch("core.inject.injector.ensure_foreground_window", return_value=1)
@patch("core.inject.injector.paste_via_clipboard")
@patch(
    "core.inject.injector.send_unicode_text",
    side_effect=InjectionFailedError("unicode failed"),
)
def test_unicode_falls_back_to_clipboard(mock_send, mock_paste, _mock_fg) -> None:
    injector = Injector(length_threshold=100)
    result = injector.inject("짧은문장", method=InjectMethod.UNICODE)
    assert result.success is True
    assert result.method_used == InjectMethod.CLIPBOARD
    mock_paste.assert_called_once()


@patch("core.inject.injector.ensure_foreground_window", return_value=1)
@patch("core.inject.injector.send_unicode_text", return_value=2)
@patch("core.inject.injector.send_backspaces")
def test_replace_last(mock_backspace, mock_send, _mock_fg) -> None:
    injector = Injector()
    result = injector.replace_last("새글", prev_text_len=3, method=InjectMethod.UNICODE)
    assert result.success is True
    mock_backspace.assert_called_once_with(3)
    mock_send.assert_called_once()


@patch("core.inject.injector.ensure_foreground_window", return_value=1)
@patch("core.inject.injector.send_enter")
@patch("core.inject.injector.send_unicode_text", return_value=1)
def test_press_enter_option(mock_send, mock_enter, _mock_fg) -> None:
    injector = Injector()
    result = injector.inject(
        "a",
        method=InjectMethod.UNICODE,
        options=InjectOptions(press_enter=True, target_check=False),
    )
    assert result.success is True
    mock_enter.assert_called_once()


def test_capabilities_windows() -> None:
    injector = Injector()
    caps = injector.capabilities()
    assert caps.platform == "windows"
    assert caps.supports_unicode is True


def test_config_create_injector(tmp_path) -> None:
    from app.config import Config

    with Config.open(tmp_path / "inject.db", migrate_backup=False) as config:
        config.set("inject.default_method", "clipboard")
        config.set("inject.length_threshold", 300)
        injector = config.create_injector()
        assert injector._default_method == InjectMethod.CLIPBOARD
        assert injector._length_threshold == 300


@patch("core.inject.injector.ensure_foreground_window", return_value=1)
@patch("core.inject.injector.send_unicode_text", return_value=2)
def test_default_method_clipboard(_mock_send, _mock_fg) -> None:
    injector = Injector(default_method=InjectMethod.CLIPBOARD)
    with patch("core.inject.injector.paste_via_clipboard") as mock_paste:
        result = injector.inject("짧은")
    assert result.success is True
    assert result.method_used == InjectMethod.CLIPBOARD
    mock_paste.assert_called_once()


@patch("core.inject.injector.paste_via_clipboard", side_effect=ClipboardBusyError("busy"))
@patch("core.inject.injector.ensure_foreground_window", return_value=1)
def test_clipboard_busy_returns_failure(_mock_fg, _mock_paste) -> None:
    injector = Injector()
    result = injector.inject("텍스트", method=InjectMethod.CLIPBOARD)
    assert result.success is False
    assert "busy" in (result.error or "")


@patch("core.inject.injector.ensure_foreground_window", return_value=1)
@patch("core.inject.injector.send_backspaces")
def test_replace_last_disabled(mock_backspace, _mock_fg) -> None:
    injector = Injector()
    result = injector.replace_last(
        "새글",
        prev_text_len=3,
        options=InjectOptions(allow_replacement=False, target_check=False),
    )
    assert result.success is False
    mock_backspace.assert_not_called()


@patch("core.inject.clipboard_input._restore_clipboard")
@patch("core.inject.clipboard_input._send_ctrl_v")
@patch("core.inject.clipboard_input.set_clipboard_text", return_value=True)
@patch("core.inject.clipboard_input.empty_clipboard", return_value=True)
@patch("core.inject.clipboard_input.close_clipboard", return_value=True)
@patch("core.inject.clipboard_input.open_clipboard", return_value=True)
@patch("core.inject.clipboard_input._read_clipboard_backup", return_value="backup")
def test_clipboard_paste_restores_backup(
    _mock_backup,
    _mock_open,
    _mock_close,
    _mock_empty,
    _mock_set,
    _mock_ctrl_v,
    mock_restore,
) -> None:
    from core.inject.clipboard_input import paste_via_clipboard

    paste_via_clipboard("주입 텍스트")
    mock_restore.assert_called_once_with("backup")


def test_config_bind_injector(tmp_path) -> None:
    from app.config import Config

    with Config.open(tmp_path / "bind_inject.db", migrate_backup=False) as config:
        injector = config.bind_injector()
        assert injector._default_method == InjectMethod.AUTO
        config.set("inject.default_method", "unicode")
        assert config._injector._default_method == InjectMethod.UNICODE
