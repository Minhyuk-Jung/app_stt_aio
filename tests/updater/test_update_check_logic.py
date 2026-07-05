"""Tests for update-check UI logic (C22 integration helpers)."""

from __future__ import annotations

from app.ui.update_check_logic import (
    build_update_prompt_lines,
    resolve_update_dialog_buttons,
    should_notify_update,
    should_offer_browser_fallback_on_download_fail,
    should_show_direct_download,
    should_show_dismiss_option,
)
from core.updater.checker import UpdateInfo


def _info(**kwargs) -> UpdateInfo:
    defaults = {
        "current_version": "0.1.0",
        "latest_version": "0.2.0",
        "download_url": "https://example.com/setup.exe",
        "release_notes": "fixes",
    }
    defaults.update(kwargs)
    return UpdateInfo(**defaults)


def test_should_notify_only_when_update_exists() -> None:
    assert should_notify_update(_info()) is True
    assert should_notify_update(None) is False


def test_direct_download_requires_checksum() -> None:
    assert should_show_direct_download(_info(checksum_sha256="a" * 64)) is True
    assert should_show_direct_download(_info(checksum_sha256=None)) is False


def test_mandatory_hides_dismiss() -> None:
    assert should_show_dismiss_option(_info(mandatory=True)) is False
    assert should_show_dismiss_option(_info(mandatory=False)) is True


def test_build_update_prompt_includes_mandatory_notice() -> None:
    lines = build_update_prompt_lines(_info(mandatory=True))
    assert any("필수 업데이트" in line for line in lines)


def test_resolve_update_dialog_buttons() -> None:
    full = resolve_update_dialog_buttons(_info(checksum_sha256="a" * 64, mandatory=False))
    assert full == {"direct_download": True, "browser": True, "dismiss": True}

    mandatory = resolve_update_dialog_buttons(_info(checksum_sha256="a" * 64, mandatory=True))
    assert mandatory["dismiss"] is False
    assert mandatory["direct_download"] is True

    browser_only = resolve_update_dialog_buttons(_info(checksum_sha256=None))
    assert browser_only == {"direct_download": False, "browser": True, "dismiss": True}


def test_browser_fallback_on_download_fail() -> None:
    assert should_offer_browser_fallback_on_download_fail(_info()) is True
    assert should_offer_browser_fallback_on_download_fail(_info(download_url="")) is False
