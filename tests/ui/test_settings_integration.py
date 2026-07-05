"""Integration tests for settings mode changes."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.config import Config
from app.ui.controller import TrayOverlayBridge
from app.ui.settings.controller import SettingsController
from core.modes.types import ModeDraft


def test_settings_active_mode_updates_config_and_bridge(tmp_path) -> None:
    config = Config.open(tmp_path / "mode-int.db", migrate_backup=False)
    runtime = MagicMock()
    runtime.config = config
    runtime.sessions = MagicMock()
    bridge = TrayOverlayBridge(runtime)
    controller = SettingsController(config)

    changes: list[tuple[str, str]] = []
    bridge.on_mode_changed(lambda mode_id, name: changes.append((mode_id, name)))

    created = controller.create_mode(
        ModeDraft(name="설정 테스트", target_stage=1, inject_stage=1)
    )
    bridge.change_mode(created.id)

    assert config.get_active_mode_id() == created.id
    assert changes[-1] == (created.id, "설정 테스트")
    config.close()
