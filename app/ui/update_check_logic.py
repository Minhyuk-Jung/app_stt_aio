"""Pure helpers for update-check UI (C22 — testable without Qt)."""

from __future__ import annotations

from core.updater.checker import UpdateInfo


def should_notify_update(info: UpdateInfo | None) -> bool:
    """Background auto-check: only surface UI when an update exists."""
    return info is not None


def build_update_prompt_lines(info: UpdateInfo) -> list[str]:
    lines = [
        f"현재: {info.current_version}",
        f"최신: {info.latest_version}",
    ]
    if info.mandatory:
        lines.append("")
        lines.append("필수 업데이트입니다. 가능한 빨리 설치해 주세요.")
    if info.release_notes:
        lines.extend(["", info.release_notes])
    return lines


def should_show_direct_download(info: UpdateInfo) -> bool:
    return info.supports_direct_download


def should_show_browser_option(info: UpdateInfo) -> bool:
    return bool(info.download_url)


def should_show_dismiss_option(info: UpdateInfo) -> bool:
    return not info.mandatory


def should_offer_browser_fallback_on_download_fail(info: UpdateInfo) -> bool:
    """C22 §7: download/verify failure → manual browser download."""
    return bool(info.download_url)


def resolve_update_dialog_buttons(info: UpdateInfo) -> dict[str, bool]:
    """Pure summary of which actions the update dialog exposes (C22 #12)."""
    return {
        "direct_download": should_show_direct_download(info),
        "browser": should_show_browser_option(info),
        "dismiss": should_show_dismiss_option(info),
    }
