"""C8 Exporter — txt/md/docx session export."""

from core.export.exporter import (
    ExportPayload,
    ExportResult,
    ExportTarget,
    TemplateInfo,
    available_templates,
    export,
    export_session,
)
from core.export.naming import build_export_filename, ensure_unique_path, sanitize_filename_part, validate_filename_pattern
from core.export.render_docx import docx_dependency_available
from core.export.templates import DEFAULT_DOCX_TEMPLATE, TEMPLATES

# Backward-compatible helpers used in early C13 P2 code/tests.
from core.export.compat import render_session_markdown
from core.export.render_txt import render_txt_body


def export_text_file(dest_path, text: str, *, encoding: str = "utf-8") -> ExportResult:
    from pathlib import Path

    from core.export.atomic import atomic_write

    path = Path(dest_path)
    try:
        atomic_write(path, lambda temp: temp.write_text(text, encoding=encoding))
        return ExportResult(path=path, format="txt", success=True)
    except OSError as exc:
        return ExportResult(
            path=path,
            format="txt",
            success=False,
            error=str(exc),
            suggestion="다른 폴더를 선택하거나 txt 형식으로 다시 시도하세요.",
        )


def export_markdown_file(
    dest_path,
    text: str,
    *,
    title: str = "",
    encoding: str = "utf-8",
) -> ExportResult:
    from pathlib import Path

    from core.export.atomic import atomic_write

    body = f"# {title}\n\n{text}" if title else text
    path = Path(dest_path)
    try:
        atomic_write(path, lambda temp: temp.write_text(body, encoding=encoding))
        return ExportResult(path=path, format="md", success=True)
    except OSError as exc:
        return ExportResult(
            path=path,
            format="md",
            success=False,
            error=str(exc),
            suggestion="다른 폴더를 선택하거나 md 형식으로 다시 시도하세요.",
        )


__all__ = [
    "DEFAULT_DOCX_TEMPLATE",
    "ExportPayload",
    "ExportResult",
    "ExportTarget",
    "TEMPLATES",
    "TemplateInfo",
    "available_templates",
    "build_export_filename",
    "docx_dependency_available",
    "ensure_unique_path",
    "export",
    "export_markdown_file",
    "export_session",
    "export_text_file",
    "render_session_markdown",
    "sanitize_filename_part",
    "validate_filename_pattern",
]
