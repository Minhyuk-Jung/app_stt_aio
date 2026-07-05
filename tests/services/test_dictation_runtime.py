"""Tests for P1 dictation runtime bootstrap."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_create_dictation_runtime_wires_components(tmp_path) -> None:
    from app.config import Config
    from app.services.dictation_runtime import create_dictation_runtime

    with Config.open(tmp_path / "runtime.db", migrate_backup=False) as config:
        with patch("core.audio.AudioCapture") as mock_capture_cls:
            capture = MagicMock()
            mock_capture_cls.return_value = capture

            runtime = create_dictation_runtime(config)

            assert runtime.config is config
            assert runtime.capture is capture
            assert runtime.hotkey is config.hotkey_manager
            assert runtime.sessions is config.session_manager
            assert config.pipeline is config.bind_pipeline()
