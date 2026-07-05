"""C21 UI-Onboarding — first-run setup wizard."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app.ui.onboarding.checks import is_completed, mark_completed

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from app.ui.settings.controller import SettingsController
    from app.ui.settings.workers import SettingsTaskRunner

OnCompletedCallback = Callable[[], None]


def start_onboarding(
    controller: SettingsController,
    *,
    tasks: SettingsTaskRunner | None = None,
    parent: QWidget | None = None,
    blocking: bool = True,
    on_completed: OnCompletedCallback | None = None,
) -> bool:
    """Show onboarding wizard (plan §3: start_onboarding, on_completed)."""
    from PySide6.QtWidgets import QDialog

    from app.ui.onboarding.onboarding_wizard import OnboardingWizard
    from app.ui.settings.workers import SettingsTaskRunner as Runner

    wizard = OnboardingWizard(
        controller,
        tasks or Runner(),
        parent=parent,
        on_completed=on_completed,
    )
    if blocking:
        return wizard.exec() == QDialog.DialogCode.Accepted
    wizard.show()
    return False


__all__ = [
    "is_completed",
    "mark_completed",
    "start_onboarding",
]
