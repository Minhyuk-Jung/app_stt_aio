"""Docx template registry (C8)."""

from __future__ import annotations

from core.export.types import TemplateInfo

TEMPLATES: dict[str, TemplateInfo] = {
    "basic": TemplateInfo(id="basic", name="기본", formats=("docx",)),
    "meeting": TemplateInfo(id="meeting", name="회의록", formats=("docx",)),
    "report": TemplateInfo(id="report", name="보고서", formats=("docx",)),
}

DEFAULT_DOCX_TEMPLATE = "basic"
DOCX_TEMPLATE_CHOICES = tuple(TEMPLATES.keys())


def available_templates(format: str) -> list[TemplateInfo]:
    return [info for info in TEMPLATES.values() if format in info.formats]


def resolve_template_id(template: str | None, *, export_format: str) -> str:
    if export_format != "docx":
        return "basic"
    template_id = template or DEFAULT_DOCX_TEMPLATE
    if template_id not in TEMPLATES:
        return DEFAULT_DOCX_TEMPLATE
    return template_id
