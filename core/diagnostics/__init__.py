"""Logging and diagnostics (C20)."""

from core.diagnostics.context import bind_context, clear_context, get_context, log_context
from core.diagnostics.diagnostics import (
    DiagnosticsExportResult,
    collect_environment,
    collect_hardware_info,
    export_diagnostics,
)
from core.diagnostics.errors import report_error, recent_errors
from core.diagnostics.logging_setup import (
    get_log_file_path,
    get_logger,
    get_memory_log_lines,
    log_event,
    set_level,
    setup_app_logging,
)

__all__ = [
    "DiagnosticsExportResult",
    "bind_context",
    "clear_context",
    "collect_environment",
    "collect_hardware_info",
    "export_diagnostics",
    "get_context",
    "get_log_file_path",
    "get_logger",
    "get_memory_log_lines",
    "log_context",
    "log_event",
    "recent_errors",
    "report_error",
    "set_level",
    "setup_app_logging",
]
