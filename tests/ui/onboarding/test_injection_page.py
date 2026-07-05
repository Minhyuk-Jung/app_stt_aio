"""InjectionPage onboarding tests (fake tasks, no Win32 injection)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ui.onboarding.checks import INJECTION_SAMPLE_TEXT
from app.ui.onboarding.steps.pages import InjectionPage
from core.inject.types import InjectMethod, InjectResult


class FakeInjectionTasks:
    def run_injection_test(self, controller, text, *, on_finished, on_failed) -> None:
        self.on_finished = on_finished
        self.on_failed = on_failed
        self.text = text


def _make_page():
    controller = MagicMock()
    tasks = FakeInjectionTasks()
    page = InjectionPage(controller, tasks)
    return page, controller, tasks


def test_injection_success_marks_verified(qtbot):
    page, _controller, tasks = _make_page()
    qtbot.addWidget(page)

    page._inject_sample()
    page._field.setText(INJECTION_SAMPLE_TEXT)
    tasks.on_finished(
        InjectResult(
            success=True,
            method_used=InjectMethod.UNICODE,
            chars_injected=len(INJECTION_SAMPLE_TEXT),
        )
    )
    qtbot.wait(150)

    assert page.injection_verified() is True
    assert page._confirmed.isChecked() is True


def test_injection_failure_shows_hint(qtbot):
    page, _controller, tasks = _make_page()
    qtbot.addWidget(page)

    page._inject_sample()
    tasks.on_finished(
        InjectResult(
            success=False,
            method_used=InjectMethod.AUTO,
            error="foreground window not found",
        )
    )

    assert page.injection_verified() is False
    assert "주입 실패" in page._status.text()
    assert "입력란" in page._status.text() or "활성" in page._status.text()
