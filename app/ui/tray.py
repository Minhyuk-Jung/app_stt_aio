"""System tray icon and menu (C12)."""

from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.ui.controller import TrayOverlayBridge


class TrayController:
    """Tray icon with quick actions; delegates to bridge."""

    def __init__(self, bridge: TrayOverlayBridge) -> None:
        self._bridge = bridge
        self._tray = QSystemTrayIcon()
        self._tray.setToolTip("STT-AIO")
        self._tray.setIcon(self._create_fallback_icon())

        menu = QMenu()
        self._action_toggle = QAction("녹음 시작/정지")
        self._action_toggle.triggered.connect(bridge.request_record_toggle)
        menu.addAction(self._action_toggle)

        action_cancel = QAction("취소")
        action_cancel.triggered.connect(bridge.request_cancel)
        menu.addAction(action_cancel)

        menu.addSeparator()

        self._mode_menu = menu.addMenu("모드")
        self._refresh_mode_menu()
        bridge.on_mode_changed(lambda _mode_id, _name: self._refresh_mode_menu())

        menu.addSeparator()

        action_settings = QAction("설정…")
        action_settings.triggered.connect(bridge.open_settings)
        menu.addAction(action_settings)

        action_workbench = QAction("작업대…")
        action_workbench.triggered.connect(bridge.open_workbench)
        menu.addAction(action_workbench)

        action_onboarding = QAction("온보딩…")
        action_onboarding.triggered.connect(bridge.open_onboarding)
        menu.addAction(action_onboarding)

        action_remote = QAction("원격 녹음…")
        action_remote.triggered.connect(bridge.open_remote_settings)
        menu.addAction(action_remote)

        action_updates = QAction("업데이트 확인…")
        action_updates.triggered.connect(bridge.check_updates)
        menu.addAction(action_updates)

        menu.addSeparator()

        action_quit = QAction("종료")
        action_quit.triggered.connect(bridge.quit_app)
        menu.addAction(action_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    def show(self) -> None:
        self._tray.show()

    def show_message(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning, 3000)

    def update_for_display_state(self, state) -> None:
        from app.ui.state_view import OverlayDisplayState

        if state is OverlayDisplayState.RECORDING:
            self._action_toggle.setEnabled(True)
            self._action_toggle.setText("녹음 정지")
        elif state is OverlayDisplayState.PROCESSING:
            self._action_toggle.setEnabled(False)
            self._action_toggle.setText("녹음 시작")
        else:
            self._action_toggle.setEnabled(True)
            self._action_toggle.setText("녹음 시작")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._bridge.request_record_toggle()

    def refresh_mode_menu(self) -> None:
        self._refresh_mode_menu()

    def _refresh_mode_menu(self) -> None:
        self._mode_menu.clear()
        active_id = self._bridge._runtime.config.get_active_mode_id()
        for mode_id, name in self._bridge.list_enabled_modes():
            action = QAction(name, self._mode_menu)
            action.setCheckable(True)
            action.setChecked(mode_id == active_id)
            action.triggered.connect(
                lambda checked=False, mid=mode_id: self._bridge.change_mode(mid)
            )
            self._mode_menu.addAction(action)

    @staticmethod
    def _create_fallback_icon() -> QIcon:
        from PySide6.QtGui import QPixmap, QPainter, QColor

        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setBrush(QColor(72, 196, 255))
        painter.setPen(QColor(20, 24, 32))
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        return QIcon(pixmap)
