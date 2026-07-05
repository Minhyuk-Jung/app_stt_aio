"""Tests for tray/settings update-check entry points (#12/#13)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_tray_check_updates_delegates_to_dialog() -> None:
    from app.ui.app_shell import TrayOverlayApp

    shell = TrayOverlayApp.__new__(TrayOverlayApp)
    shell._runtime = MagicMock()
    shell._runtime.config.get.return_value = "https://cdn.example/manifest.json"
    shell._update_tasks = MagicMock()

    with patch("app.ui.app_shell.run_update_check_dialog") as dialog:
        TrayOverlayApp._check_updates(shell)

    dialog.assert_called_once_with(
        shell._update_tasks,
        "https://cdn.example/manifest.json",
        None,
    )


def test_general_settings_check_updates_delegates_to_dialog(qapp) -> None:
    from app.ui.settings.pages import GeneralSettingsPage

    controller = MagicMock()
    controller.get_setting.return_value = "https://cdn.example/manifest.json"
    controller.get_choice_keys.return_value = ["default"]
    controller.list_audio_devices.return_value = []
    tasks = MagicMock()

    page = GeneralSettingsPage(controller, tasks=tasks)

    with patch("app.ui.update_check.run_update_check_dialog") as dialog:
        page._check_updates()

    dialog.assert_called_once_with(
        tasks,
        "https://cdn.example/manifest.json",
        page,
    )
