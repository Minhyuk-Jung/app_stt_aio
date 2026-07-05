"""Settings window shell (C14)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout

from app.ui.settings.pages import (
    DictionarySettingsPage,
    ExportSettingsPage,
    GeneralSettingsPage,
    HotkeySettingsPage,
    LlmSettingsPage,
    ModelsSettingsPage,
    ModesSettingsPage,
    PrivacySettingsPage,
    RemoteSettingsPage,
    SttSettingsPage,
    TextprocSettingsPage,
)
from app.ui.settings.workers import SettingsTaskRunner

if TYPE_CHECKING:
    from app.services.remote_gateway_service import RemoteGatewayService
    from app.ui.settings.controller import SettingsController

ActiveModeCallback = Callable[[str, str], None]
ModesChangedCallback = Callable[[], None]


class SettingsWindow(QDialog):
    """Tabbed settings dialog (P2: STT/LLM/Hotkey/Modes + connection test)."""

    def __init__(
        self,
        controller: SettingsController,
        *,
        gateway_service: RemoteGatewayService | None = None,
        on_active_mode_changed: ActiveModeCallback | None = None,
        on_modes_changed: ModesChangedCallback | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._gateway_service = gateway_service
        self._tasks = SettingsTaskRunner()
        self.setWindowTitle("STT-AIO 설정")
        self.setMinimumSize(720, 520)

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._pages: list = []

        page_defs = [
            ("일반", lambda: GeneralSettingsPage(controller, self._tasks)),
            ("STT", lambda: SttSettingsPage(controller, self._tasks)),
            ("LLM", lambda: LlmSettingsPage(controller, self._tasks)),
            ("핫키", lambda: HotkeySettingsPage(controller)),
            ("텍스트 후처리", lambda: TextprocSettingsPage(controller)),
            ("사전·스니펫", lambda: DictionarySettingsPage(controller)),
            (
                "모드",
                lambda: ModesSettingsPage(
                    controller,
                    on_active_mode_changed=on_active_mode_changed,
                    on_modes_changed=on_modes_changed,
                ),
            ),
            ("프라이버시", lambda: PrivacySettingsPage(controller)),
            ("원격 녹음", lambda: RemoteSettingsPage(controller, self._gateway_service)),
            ("보내기", lambda: ExportSettingsPage(controller)),
            ("모델", lambda: ModelsSettingsPage(controller, self._tasks)),
        ]
        for title, factory in page_defs:
            page = factory()
            self._pages.append(page)
            self._tabs.addTab(page, title)
        layout.addWidget(self._tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        for page in self._pages:
            if hasattr(page, "reload"):
                page.reload()

    def select_tab(self, title: str) -> None:
        for index in range(self._tabs.count()):
            if self._tabs.tabText(index) == title:
                self._tabs.setCurrentIndex(index)
                return
