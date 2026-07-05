"""Tests for hotkey + session integration."""

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


def test_wire_hotkey_runs_batch_session(tmp_path) -> None:
    from app.config import Config

    config = Config.open(tmp_path / "hotkey_session.db", migrate_backup=False)
    backend = MockKeyboardBackend()
    hotkey = HotkeyManager(backend=backend)
    hotkey.register(
        HotkeyBinding(id="record", keys="ctrl+space", action=HotkeyAction.RECORD)
    )
    hotkey.start()

    capture = MagicMock()
    handle = MagicMock()
    capture.start_batch.return_value = handle
    capture.stop_batch.return_value = AudioBuffer(pcm_bytes=b"\x00\x01")

    session_manager = SessionManager(config, capture)
    session_manager.wire_hotkey(hotkey)

    states: list[SessionStatus] = []
    session_manager.on_session_state(lambda _sid, status: states.append(status))

    artifact = SessionArtifact(
        session_id="test",
        stage=1,
        text="테스트",
        language="ko",
        inject_result=MagicMock(success=True),
    )

    with patch(
        "app.session.session_manager.run_batch_pipeline",
        return_value=(STTResult(text="테스트", language="ko"), artifact),
    ):
        press(backend, VK_CTRL)
        press(backend, VK_SPACE)
        release(backend, VK_SPACE)

        deadline = time.time() + 2.0
        while time.time() < deadline:
            if SessionStatus.DONE in states:
                break
            time.sleep(0.02)

    assert SessionStatus.RECORDING in states
    assert SessionStatus.DONE in states
    capture.start_batch.assert_called_once()
    capture.stop_batch.assert_called_once_with(handle)

    hotkey.close()
    session_manager.close()
    config.close()
