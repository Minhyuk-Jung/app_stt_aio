"""UI package (C12)."""

from app.ui.controller import TrayOverlayBridge, UiActionHandlers
from app.ui.state_view import OverlayDisplayState, map_session_status, overlay_status_text
from app.ui.waveform_buffer import WaveformBuffer

__all__ = [
    "OverlayDisplayState",
    "TrayOverlayBridge",
    "UiActionHandlers",
    "WaveformBuffer",
    "map_session_status",
    "overlay_status_text",
]


def create_tray_overlay_app(runtime):
    """Create tray+overlay app (requires PySide6: pip install stt-aio[ui])."""
    from app.ui.app_shell import create_tray_overlay_app as _create

    return _create(runtime)
