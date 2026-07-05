"""Stage inject adapter for C4 (uses C5 Injector via Config)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.inject.types import InjectMethod, InjectResult

if TYPE_CHECKING:
    from app.config.config import Config


def inject_stage_text(
    config: Config,
    text: str,
    *,
    inject_method: str | None = None,
    press_enter: bool | None = None,
) -> InjectResult:
    """Inject pipeline stage text at the cursor."""
    if config._injector is None:
        config.bind_injector()

    if not text.strip():
        return InjectResult(
            success=True,
            method_used=InjectMethod.UNICODE,
            chars_injected=0,
        )

    options = config.get_inject_options()
    if press_enter is not None:
        options.press_enter = press_enter

    return config.injector.inject(
        text,
        method=inject_method,
        options=options,
    )
