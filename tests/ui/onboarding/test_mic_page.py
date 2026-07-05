"""Regression tests for MicPage probe UI (fake tasks, no hardware)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ui.onboarding.steps.pages import MicPage
from app.ui.settings.controller import ReadinessResult


class FakeMicTasks:
    def run_mic_probe(
        self, controller, device_id, *, on_finished, on_failed, on_level=None
    ) -> None:
        self.on_finished = on_finished
        self.on_failed = on_failed
        self.on_level = on_level


def _make_page():
    controller = MagicMock()
    controller.list_audio_devices.return_value = [
        MagicMock(label="Mic 1", device_id="mic-1"),
    ]
    controller.get_setting.return_value = "mic-1"
    tasks = FakeMicTasks()
    page = MicPage(controller, tasks)
    return page, controller, tasks


def test_mic_probe_success_updates_status(qtbot):
    page, _controller, tasks = _make_page()
    qtbot.addWidget(page)
    page.initializePage()

    page._run_test()
    tasks.on_finished(ReadinessResult(True, "마이크 입력 확인 (peak=42%)"))

    assert page.mic_tested() is True
    assert "✓" in page._status.text()
    assert page._level.value() == 42


def test_mic_probe_failure_shows_error(qtbot):
    page, _controller, tasks = _make_page()
    qtbot.addWidget(page)
    page.initializePage()

    page._run_test()
    tasks.on_finished(ReadinessResult(False, "입력 신호가 거의 감지되지 않았습니다."))

    assert page.mic_tested() is False
    assert "✗" in page._status.text()
