"""Regression tests for ModelPage download progress (0% stuck bug)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ui.onboarding.checks import RECOMMENDED_WHISPER_MODEL
from app.ui.onboarding.steps.pages import ModelPage


class FakeTasks:
    """Capture callbacks so the test can drive them synchronously (no threads)."""

    def run_whisper_download(
        self, controller, model_id, *, on_progress, on_finished, on_failed, force=False
    ) -> None:
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.on_failed = on_failed


def _make_page():
    controller = MagicMock()
    controller.get_models_dir.return_value = "/models"
    controller.get_models_custom_path.return_value = ""
    tasks = FakeTasks()
    page = ModelPage(controller, tasks)
    return page, controller, tasks


def test_download_updates_progress_bar(qtbot):
    page, _controller, tasks = _make_page()
    qtbot.addWidget(page)

    page._download_recommended()
    tasks.on_progress(30, 100, "downloading")

    assert page._progress.value() == 30
    assert "30%" in page._progress_label.text()


def test_download_finished_sets_active_model(qtbot):
    page, controller, tasks = _make_page()
    qtbot.addWidget(page)

    page._download_recommended()
    tasks.on_finished("/models/base")

    controller.set_active_whisper_model.assert_called_with(RECOMMENDED_WHISPER_MODEL)
    assert page._progress.isVisible() is False


def test_download_failure_shows_retry(qtbot):
    page, _controller, tasks = _make_page()
    qtbot.addWidget(page)

    page._download_recommended()
    tasks.on_failed("network error")

    assert not page._retry_btn.isHidden()
