"""Tests for auto_send hotkey wiring through session manager."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from app.hotkey.backend import MockKeyboardBackend
from app.hotkey.hotkey_manager import HotkeyManager
from app.hotkey.types import HotkeyAction, HotkeyBinding
from app.session import SessionManager
from app.session.types import SessionArtifact
from core.audio.format import AudioBuffer
from core.stt.types import STTResult
from core.store.models import SessionStatus
from tests.hotkey.helpers import VK_CTRL, VK_SPACE, press, release


def test_auto_send_passes_press_enter_to_pipeline(tmp_path) -> None:
    from app.config import Config

    config = Config.open(tmp_path / "auto_send.db", migrate_backup=False)
    backend = MockKeyboardBackend()
    hotkey = HotkeyManager(backend=backend, auto_send_enabled=True)
    hotkey.register(
        HotkeyBinding(id="record", keys="ctrl+space", action=HotkeyAction.RECORD)
    )
    hotkey.start()

    capture = MagicMock()
    handle = MagicMock()
    capture.start_batch.return_value = handle
    capture.stop_batch.return_value = AudioBuffer(pcm_bytes=b"\x00\x01")

    sessions = SessionManager(config, capture)
    sessions.wire_hotkey(hotkey)

    artifact = SessionArtifact(session_id="x", stage=1, text="hi", language="ko")
    with patch(
        "app.session.session_manager.run_batch_pipeline",
        return_value=(STTResult(text="hi", language="ko"), artifact),
    ) as mock_pipeline:
        press(backend, VK_CTRL)
        press(backend, 0xA4)  # alt
        press(backend, VK_SPACE)
        release(backend, VK_SPACE)

        deadline = time.time() + 2.0
        while time.time() < deadline:
            if mock_pipeline.call_args is not None:
                break
            time.sleep(0.02)

    assert mock_pipeline.call_args is not None
    assert mock_pipeline.call_args.kwargs.get("press_enter") is True

    hotkey.close()
    sessions.close()
    config.close()
