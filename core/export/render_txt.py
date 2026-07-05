"""Plain-text export rendering (C8)."""

from __future__ import annotations

from core.export.stages import stage_heading
from core.export.types import ExportPayload


def render_txt_body(
    payload: ExportPayload,
    *,
    stages: tuple[int, ...],
    include_meta: bool,
) -> str:
    lines: list[str] = []
    if include_meta:
        lines.extend(
            [
                f"session: {payload.session_id}",
                f"mode: {payload.mode_name}",
                f"created: {payload.created_at.strftime('%Y-%m-%d %H:%M')}",
                "",
            ]
        )
    selected = [stage for stage in stages if stage in payload.stages]
    if len(selected) == 1:
        return "\n".join(lines) + payload.stages[selected[0]]
    for stage in selected:
        lines.append(f"[{stage_heading(stage)}]")
        lines.append(payload.stages[stage])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
