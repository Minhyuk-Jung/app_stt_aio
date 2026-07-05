"""UI-layer tests for C22 update check (#12/#13) without live network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ui.update_check import _show_result, run_update_check_dialog
from core.updater.checker import UpdateInfo


def _info(**kwargs) -> UpdateInfo:
    defaults = {
        "current_version": "0.1.0",
        "latest_version": "0.2.0",
        "download_url": "https://cdn.example/STT-AIO-Setup-0.2.0.exe",
        "release_notes": "fixes",
        "checksum_sha256": "a" * 64,
    }
    defaults.update(kwargs)
    return UpdateInfo(**defaults)


def test_show_result_triggers_download_when_accept_clicked() -> None:
    tasks = MagicMock()
    info = _info()
    box = MagicMock()
    btn_download = MagicMock()
    btn_browser = MagicMock()
    box.clickedButton.return_value = btn_download
    box.addButton.side_effect = [btn_download, btn_browser]

    with patch("app.ui.update_check.QMessageBox", return_value=box):
        with patch("app.ui.update_check.should_show_direct_download", return_value=True):
            with patch("app.ui.update_check.should_show_browser_option", return_value=True):
                with patch("app.ui.update_check.should_show_dismiss_option", return_value=False):
                    with patch("app.ui.update_check._run_download_and_install") as run_dl:
                        _show_result(None, info, tasks, silent_if_current=False)

    run_dl.assert_called_once_with(None, info, tasks)


def test_show_result_opens_browser_when_browser_clicked() -> None:
    tasks = MagicMock()
    info = _info(checksum_sha256=None)
    box = MagicMock()
    btn_browser = MagicMock()
    box.clickedButton.return_value = btn_browser
    box.addButton.side_effect = [btn_browser]

    with patch("app.ui.update_check.QMessageBox", return_value=box):
        with patch("app.ui.update_check.should_show_direct_download", return_value=False):
            with patch("app.ui.update_check.should_show_browser_option", return_value=True):
                with patch("app.ui.update_check.should_show_dismiss_option", return_value=False):
                    with patch("app.ui.update_check.webbrowser.open") as open_url:
                        _show_result(None, info, tasks, silent_if_current=False)

    open_url.assert_called_once_with(info.download_url)


def test_run_update_check_dialog_warns_when_manifest_url_empty() -> None:
    tasks = MagicMock()

    with patch("app.ui.update_check.QMessageBox.information") as info_box:
        run_update_check_dialog(tasks, "", None)

    info_box.assert_called_once()
    tasks.run_update_check.assert_not_called()


def test_show_result_silent_when_no_update() -> None:
    tasks = MagicMock()
    with patch("app.ui.update_check.QMessageBox.information") as info_box:
        _show_result(None, None, tasks, silent_if_current=True)
    info_box.assert_not_called()


def test_run_download_and_install_registers_worker_callbacks() -> None:
    from app.ui.update_check import _run_download_and_install

    tasks = MagicMock()
    tasks.try_begin_update_download.return_value = True
    info = _info()
    captured: dict = {}

    def _capture_run(info_arg, dest, *, on_progress, on_finished, on_failed):
        captured["dest"] = dest
        captured["on_finished"] = on_finished
        captured["on_failed"] = on_failed

    tasks.run_update_download.side_effect = _capture_run
    progress = MagicMock()

    with patch("app.ui.update_check.QProgressDialog", return_value=progress):
        with patch("app.ui.update_check.QMessageBox"):
            _run_download_and_install(None, info, tasks)

    tasks.run_update_download.assert_called_once()
    assert "0.2.0" in captured["dest"]


def test_run_download_and_install_browser_fallback_on_failure() -> None:
    from PySide6.QtWidgets import QMessageBox

    from app.ui.update_check import _run_download_and_install

    tasks = MagicMock()
    tasks.try_begin_update_download.return_value = True
    info = _info()
    captured: dict = {}

    def _capture_run(info_arg, dest, *, on_progress, on_finished, on_failed):
        captured["on_failed"] = on_failed

    tasks.run_update_download.side_effect = _capture_run
    progress = MagicMock()

    with patch("app.ui.update_check.QProgressDialog", return_value=progress):
        with patch(
            "app.ui.update_check.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            with patch("app.ui.update_check.webbrowser.open") as open_url:
                _run_download_and_install(None, info, tasks)
                captured["on_failed"]("network error")

    open_url.assert_called_once_with(info.download_url)
    tasks.end_update_download.assert_called()


def test_run_download_and_install_apply_update_on_confirm() -> None:
    from PySide6.QtWidgets import QMessageBox

    from app.ui.update_check import _run_download_and_install

    tasks = MagicMock()
    tasks.try_begin_update_download.return_value = True
    info = _info()
    captured: dict = {}

    def _capture_run(info_arg, dest, *, on_progress, on_finished, on_failed):
        captured["on_finished"] = on_finished

    tasks.run_update_download.side_effect = _capture_run
    progress = MagicMock()
    app = MagicMock()

    with patch("app.ui.update_check.QProgressDialog", return_value=progress):
        with patch(
            "app.ui.update_check.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            with patch("app.ui.update_check.apply_update") as apply_update:
                with patch("app.ui.update_check.QApplication.instance", return_value=app):
                    _run_download_and_install(None, info, tasks)
                    captured["on_finished"]("C:\\Temp\\STT-AIO-Setup-0.2.0.exe")

    apply_update.assert_called_once()
    app.quit.assert_called_once()
    tasks.end_update_download.assert_called()


def test_startup_update_check_skips_when_no_manifest() -> None:
    from app.ui.update_check import run_update_check_on_startup

    tasks = MagicMock()
    run_update_check_on_startup(tasks, "  ", None)
    tasks.run_update_check.assert_not_called()
