"""Backward-compatible markdown render helper."""

from __future__ import annotations

from datetime import datetime

from core.export.render_md import render_md_body
from core.export.types import ExportPayload


def render_session_markdown(
    *,
    session_id: str,
    mode_name: str,
    created_at: str,
    stages: dict[int, str],
    include_meta: bool,
) -> str:
    payload = ExportPayload(
        session_id=session_id,
        mode_name=mode_name,
        created_at=datetime.strptime(created_at, "%Y-%m-%d %H:%M"),
        stages=stages,
    )
    return render_md_body(
        payload,
        stages=tuple(sorted(stages)),
        include_meta=include_meta,
    )
