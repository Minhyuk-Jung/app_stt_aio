"""Shared update-check UI (C22 step 1 + §6.2 download/apply)."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog, QWidget

from app.ui.settings.workers import SettingsTaskRunner
from app.ui.update_check_logic import (
    build_update_prompt_lines,
    should_notify_update,
    should_show_browser_option,
    should_show_direct_download,
    should_show_dismiss_option,
)
from core.updater.checker import UpdateInfo
from core.updater.downloader import apply_update, default_installer_path
from core.version import __version__


def run_update_check_dialog(
    tasks: SettingsTaskRunner,
    manifest_url: str,
    parent: QWidget | None,
) -> None:
    """Manual update check from tray/settings."""
    _start_update_check(tasks, manifest_url, parent, silent_if_current=False)


def run_update_check_on_startup(
    tasks: SettingsTaskRunner,
    manifest_url: str,
    parent: QWidget | None,
) -> None:
    """Background check on app start — only prompts when an update exists."""
    _start_update_check(tasks, manifest_url, parent, silent_if_current=True)


def _start_update_check(
    tasks: SettingsTaskRunner,
    manifest_url: str,
    parent: QWidget | None,
    *,
    silent_if_current: bool,
) -> None:
    url = manifest_url.strip()
    if not url:
        if not silent_if_current:
            QMessageBox.information(
                parent,
                "업데이트",
                "설정 → 일반 탭에서 업데이트 매니페스트 URL을 입력하세요.",
            )
        return

    def on_finished(info) -> None:
        if silent_if_current and not should_notify_update(info):
            return
        _show_result(parent, info, tasks, silent_if_current=silent_if_current)

    def on_failed(message: str) -> None:
        if silent_if_current:
            return
        QMessageBox.warning(parent, "업데이트 확인 실패", message)

    tasks.run_update_check(url, on_finished=on_finished, on_failed=on_failed)


def _show_result(
    parent: QWidget | None,
    info: UpdateInfo | None,
    tasks: SettingsTaskRunner,
    *,
    silent_if_current: bool,
) -> None:
    if info is None:
        if silent_if_current:
            return
        QMessageBox.information(
            parent,
            "업데이트",
            f"현재 버전({__version__})이 최신이거나 매니페스트를 확인할 수 없습니다.",
        )
        return

    if not info.download_url and not info.release_notes:
        QMessageBox.information(parent, "업데이트 사용 가능", _format_lines(info))
        return

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning if info.mandatory else QMessageBox.Icon.Information)
    box.setWindowTitle("필수 업데이트" if info.mandatory else "업데이트 사용 가능")
    box.setText(_format_lines(info))

    btn_download = None
    btn_browser = None
    if should_show_direct_download(info):
        btn_download = box.addButton("다운로드 및 설치", QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(btn_download)
    if should_show_browser_option(info):
        btn_browser = box.addButton("브라우저에서 열기", QMessageBox.ButtonRole.ActionRole)
    if should_show_dismiss_option(info):
        box.addButton("나중에", QMessageBox.ButtonRole.RejectRole)

    box.exec()
    clicked = box.clickedButton()
    if clicked is btn_download and should_show_direct_download(info):
        _run_download_and_install(parent, info, tasks)
    elif clicked is btn_browser and info.download_url:
        webbrowser.open(info.download_url)


def _format_lines(info: UpdateInfo) -> str:
    return "\n".join(build_update_prompt_lines(info))


def _run_download_and_install(
    parent: QWidget | None,
    info: UpdateInfo,
    tasks: SettingsTaskRunner,
) -> None:
    if not tasks.try_begin_update_download():
        QMessageBox.information(parent, "업데이트", "이미 다운로드가 진행 중입니다.")
        return

    dest = default_installer_path(info.latest_version)

    progress = QProgressDialog("업데이트 다운로드 중…", None, 0, 100, parent)
    progress.setWindowTitle("업데이트")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setValue(0)
    progress.show()

    def on_progress(downloaded: int, total: int, state: str) -> None:
        if total > 0:
            progress.setMaximum(total)
            progress.setValue(min(downloaded, total))
        label_total = str(total) if total > 0 else "?"
        progress.setLabelText(f"{state}: {downloaded} / {label_total} bytes")

    def on_finished(path_str: str) -> None:
        tasks.end_update_download()
        progress.close()
        answer = QMessageBox.question(
            parent,
            "다운로드 완료",
            "설치 프로그램을 실행할까요?\n\n"
            f"{path_str}\n\n"
            "설치를 위해 앱이 종료됩니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            apply_update(Path(path_str))
        except OSError as exc:
            QMessageBox.warning(parent, "설치 실행 실패", str(exc))
            return
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def on_failed(message: str) -> None:
        tasks.end_update_download()
        progress.close()
        if info.download_url:
            answer = QMessageBox.question(
                parent,
                "다운로드 실패",
                f"{message}\n\n브라우저에서 수동으로 다운로드할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                webbrowser.open(info.download_url)
            return
        QMessageBox.warning(parent, "다운로드 실패", message)

    tasks.run_update_download(
        info,
        str(dest),
        on_progress=on_progress,
        on_finished=on_finished,
        on_failed=on_failed,
    )
