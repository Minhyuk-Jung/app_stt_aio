"""C13 Workbench UI."""

from app.ui.workbench.controller import WorkbenchController

__all__ = ["WorkbenchController"]


def __getattr__(name: str):
    if name == "WorkbenchWindow":
        from app.ui.workbench.workbench_window import WorkbenchWindow

        return WorkbenchWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
