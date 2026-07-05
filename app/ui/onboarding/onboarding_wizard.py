"""Onboarding wizard controller (C21 plan §6.1)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWizard

from app.ui.onboarding.steps import (
    DonePage,
    HotkeyPage,
    InjectionPage,
    MicPage,
    ModelPage,
    ProviderPage,
    WelcomePage,
)
from app.ui.settings.controller import SettingsController
from app.ui.settings.workers import SettingsTaskRunner

OnCompletedCallback = Callable[[], None]


class OnboardingWizard(QWizard):
    """First-run setup: Welcome → Provider → Model → Mic → Injection → Hotkey → Done."""

    def __init__(
        self,
        controller: SettingsController,
        tasks: SettingsTaskRunner,
        *,
        parent=None,
        on_completed: OnCompletedCallback | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._tasks = tasks
        self._on_completed = on_completed
        self._skipping = False

        self.setWindowTitle("STT-AIO 설정 마법사")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveCustomButton1, True)
        self.setButtonText(QWizard.WizardButton.CustomButton1, "건너뛰기")
        self.button(QWizard.WizardButton.CustomButton1).clicked.connect(self._skip_current)
        self.currentIdChanged.connect(self._update_skip_button)

        self.addPage(WelcomePage(self))
        self.addPage(ProviderPage(controller, tasks, self))
        self.addPage(ModelPage(controller, tasks, self))
        self.addPage(MicPage(controller, tasks, self))
        self.addPage(InjectionPage(controller, tasks, self))
        self.addPage(HotkeyPage(controller, self))
        self.addPage(DonePage(controller, self))

        self.finished.connect(self._on_finished)
        self._update_skip_button(self.pageIds()[0])

    def is_skipping(self) -> bool:
        return self._skipping

    def _skip_current(self) -> None:
        if self.currentId() >= self.pageIds()[-1]:
            return
        self._skipping = True
        try:
            self.next()
        finally:
            self._skipping = False

    def _update_skip_button(self, page_id: int) -> None:
        first_id = self.pageIds()[0]
        last_id = self.pageIds()[-1]
        skip_btn = self.button(QWizard.WizardButton.CustomButton1)
        page = self.page(page_id)
        hide_for_injection = isinstance(page, InjectionPage)
        skip_btn.setVisible(page_id not in (first_id, last_id) and not hide_for_injection)

    def _on_finished(self, result: int) -> None:
        if result != int(QWizard.DialogCode.Accepted):
            return
        self._controller.apply_hotkey_bindings()
        self._controller.mark_onboarding_completed()
        if self._on_completed is not None:
            self._on_completed()
