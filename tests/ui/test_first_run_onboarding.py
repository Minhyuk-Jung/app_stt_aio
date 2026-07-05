"""First-run onboarding trigger without showing tray (mocked runtime)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.config import Config
from app.ui.app_shell import TrayOverlayApp


def test_first_run_opens_onboarding(qtbot, tmp_path):
    config = Config.open(tmp_path / "first_run.db", migrate_backup=False)
    runtime = MagicMock()
    runtime.config = config
    runtime.hotkey = MagicMock()
    runtime.sessions = MagicMock()

    app = TrayOverlayApp(runtime)
    qtbot.addWidget(app._overlay)

    opened: list[str] = []

    with patch.object(app, "_open_onboarding", side_effect=lambda: opened.append("onboarding")):
        with patch("app.ui.app_shell.start_hotkey_safe", return_value=True):
            app._tray.show = MagicMock()
            app._app.exec = MagicMock(return_value=0)
            app.run()

    assert opened == ["onboarding"]
    config.close()
