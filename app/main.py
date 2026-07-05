"""STT-AIO desktop entry point."""

from __future__ import annotations

import sys


def main() -> int:
    if "--version" in sys.argv:
        from core.version import __version__

        print(__version__)
        return 0

    from core.diagnostics import setup_app_logging
    from core.paths import ensure_app_dirs, get_app_paths

    bootstrap_paths = ensure_app_dirs(get_app_paths())
    setup_app_logging(bootstrap_paths.logs, level="info")

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except ImportError as exc:
        from core.runtime import is_frozen

        if is_frozen():
            import traceback

            print(
                f"PySide6 import failed in packaged build: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc()
        else:
            print(
                "PySide6 is required for the desktop UI. Install with: pip install stt-aio[ui]",
                file=sys.stderr,
            )
        return 1

    from app.config import Config
    from app.services.dictation_runtime import create_dictation_runtime
    from app.ui.app_shell import create_tray_overlay_app

    with Config.open() as config:
        runtime = create_dictation_runtime(config)
        app = create_tray_overlay_app(runtime)
        return app.run()


def _report_startup_failure(error: BaseException) -> int:
    from core.runtime import is_frozen, startup_failure_message

    message = startup_failure_message(error)
    if is_frozen():
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication(sys.argv)
            QMessageBox.critical(None, "STT-AIO", message)
        except Exception:
            print(message, file=sys.stderr)
    else:
        print(message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        raise SystemExit(_report_startup_failure(exc))
