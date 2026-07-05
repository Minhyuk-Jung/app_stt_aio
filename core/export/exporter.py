"""C8 Exporter entry point."""

from __future__ import annotations

import logging
from pathlib import Path

from core.export.atomic import atomic_write
from core.export.render_docx import docx_dependency_available, render_docx_document
from core.export.render_md import render_md_body
from core.export.render_txt import render_txt_body
from core.export.templates import available_templates, resolve_template_id
from core.export.types import ExportPayload, ExportResult, ExportTarget, TemplateInfo

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = frozenset({"txt", "md", "docx"})
TXT_ENCODING = "utf-8-sig"
MD_ENCODING = "utf-8"


def export(
    target: ExportTarget,
    dest_path: Path,
    export_format: str,
    payload: ExportPayload,
) -> ExportResult:
    """Plan §3 public entry: export(target, format, dest_path) with resolved payload."""
    return export_session(payload, target, dest_path, export_format)


def export_session(
    payload: ExportPayload,
    target: ExportTarget,
    dest_path: Path,
    export_format: str,
) -> ExportResult:
    """Render session artifacts to dest_path (atomic write)."""
    fmt = export_format.lower().strip()
    if fmt not in SUPPORTED_FORMATS:
        return ExportResult(
            path=dest_path,
            format=export_format,
            success=False,
            error=f"unsupported format '{export_format}'",
            suggestion="txt, md, docx 중 하나를 선택하세요.",
        )

    stages = tuple(stage for stage in target.stages if stage in payload.stages)
    if not stages:
        return ExportResult(
            path=dest_path,
            format=fmt,
            success=False,
            error="no exportable stage content",
            suggestion="산출물이 있는 stage를 선택하세요.",
        )

    if any(not payload.stages[stage].strip() for stage in stages):
        return ExportResult(
            path=dest_path,
            format=fmt,
            success=False,
            error="empty stage text cannot be exported",
            suggestion="내용이 있는 산출물을 선택하세요.",
        )

    try:
        if fmt == "txt":
            body = render_txt_body(
                payload,
                stages=stages,
                include_meta=target.include_meta,
            )
            atomic_write(
                dest_path,
                lambda temp: temp.write_text(body, encoding=TXT_ENCODING),
            )
        elif fmt == "md":
            body = render_md_body(
                payload,
                stages=stages,
                include_meta=target.include_meta,
            )
            atomic_write(
                dest_path,
                lambda temp: temp.write_text(body, encoding=MD_ENCODING),
            )
        else:
            if not docx_dependency_available():
                return ExportResult(
                    path=dest_path,
                    format=fmt,
                    success=False,
                    error="python-docx is not installed",
                    suggestion="pip install -e \".[export]\" 후 docx를 사용하세요. txt/md로 다시 시도할 수 있습니다.",
                )
            template_id = resolve_template_id(target.template, export_format=fmt)
            document = render_docx_document(
                payload,
                stages=stages,
                include_meta=target.include_meta,
                template_id=template_id,
            )
            atomic_write(dest_path, lambda temp: document.save(str(temp)))

        return ExportResult(path=dest_path, format=fmt, success=True)
    except OSError as exc:
        logger.warning("export failed for %s: %s", dest_path, exc)
        return ExportResult(
            path=dest_path,
            format=fmt,
            success=False,
            error=str(exc),
            suggestion="다른 폴더를 선택하거나 txt/md 형식으로 다시 시도하세요.",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("export render failed")
        suggestion = "txt 또는 md 형식으로 다시 시도하세요."
        if fmt == "docx":
            suggestion = "txt/md로 다시 시도하거나 python-docx 설치를 확인하세요."
        return ExportResult(
            path=dest_path,
            format=fmt,
            success=False,
            error=str(exc),
            suggestion=suggestion,
        )


__all__ = [
    "ExportPayload",
    "ExportResult",
    "ExportTarget",
    "TemplateInfo",
    "available_templates",
    "export",
    "export_session",
]
