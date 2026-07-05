"""Markdown export rendering (C8)."""

from __future__ import annotations

from core.export.stages import stage_heading
from core.export.types import ExportPayload


def render_md_body(
    payload: ExportPayload,
    *,
    stages: tuple[int, ...],
    include_meta: bool,
) -> str:
    lines: list[str] = []
    if include_meta:
        lines.extend(
            [
                f"# {payload.mode_name}",
                "",
                f"- session: `{payload.session_id}`",
                f"- mode: {payload.mode_name}",
                f"- created: {payload.created_at.strftime('%Y-%m-%d %H:%M')}",
                "",
            ]
        )
    elif len(stages) == 1:
        lines.extend([f"# {payload.mode_name}", ""])

    for stage in stages:
        if stage not in payload.stages:
            continue
        text = payload.stages[stage]
        lines.append(f"## {stage_heading(stage)}")
        lines.append("")
        lines.extend(_format_stage_markdown(text))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_stage_markdown(text: str) -> list[str]:
    """Preserve paragraph breaks; promote simple bullet lines."""
    output: list[str] = []
    for block in text.split("\n\n"):
        stripped = block.strip()
        if not stripped:
            continue
        if all(line.strip().startswith(("- ", "* ")) for line in stripped.splitlines() if line.strip()):
            output.extend(line.rstrip() for line in stripped.splitlines())
        else:
            output.append(stripped)
    return output
