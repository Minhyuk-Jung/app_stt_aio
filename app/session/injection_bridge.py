"""Pipeline inject events to C5 Injector (C10)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.pipeline.inject import inject_stage_text
from core.inject.types import InjectResult

if TYPE_CHECKING:
    from app.config.config import Config


def inject_transcript(
    config: Config,
    text: str,
    *,
    inject_method: str | None = None,
    press_enter: bool | None = None,
) -> InjectResult:
    """Inject transcript text at the cursor using configured options."""
    return inject_stage_text(
        config,
        text,
        inject_method=inject_method,
        press_enter=press_enter,
    )
