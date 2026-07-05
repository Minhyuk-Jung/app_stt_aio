"""Export template definitions (C8 plan §6.1)."""

from core.export.templates.registry import (
    DEFAULT_DOCX_TEMPLATE,
    DOCX_TEMPLATE_CHOICES,
    TEMPLATES,
    available_templates,
    resolve_template_id,
)

__all__ = [
    "DEFAULT_DOCX_TEMPLATE",
    "DOCX_TEMPLATE_CHOICES",
    "TEMPLATES",
    "available_templates",
    "resolve_template_id",
]
