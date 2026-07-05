"""C14 Settings / Modes UI."""

from app.ui.settings.controller import SettingsController

__all__ = ["SettingsController"]


def __getattr__(name: str):
    if name == "SettingsWindow":
        from app.ui.settings.settings_window import SettingsWindow

        return SettingsWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
