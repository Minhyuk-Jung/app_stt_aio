"""P1 batch dictation service via C4 Pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.session.orchestration import run_batch_pipeline
from core.audio.format import AudioBuffer
from core.store.models import SessionSource, SessionStatus

if TYPE_CHECKING:
    from app.config.config import Config
    from core.inject.types import InjectResult
    from core.stt.types import STTResult


@dataclass(frozen=True)
class BatchDictationResult:
    stt: STTResult
    inject: InjectResult | None
    session_id: str


def transcribe_and_inject(
    config: Config,
    audio: AudioBuffer,
    *,
    session_id: str | None = None,
    inject_method: str | None = None,
) -> BatchDictationResult:
    """Run configured batch dictation through the shared C4 pipeline."""
    ephemeral = session_id is None
    if ephemeral:
        stored = config._store.sessions.create(
            source=SessionSource.BATCH,
            mode_id=config.get_active_mode_id(),
            status=SessionStatus.PROCESSING,
        )
        session_id = stored.id

    try:
        stt_result, artifact = run_batch_pipeline(
            config,
            session_id,
            audio,
            inject_method=inject_method,
        )
        if ephemeral:
            status = (
                SessionStatus.ERROR
                if artifact.inject_result is not None and not artifact.inject_result.success
                else SessionStatus.DONE
            )
            config._store.sessions.update_status(session_id, status)

        return BatchDictationResult(
            stt=stt_result,
            inject=artifact.inject_result,
            session_id=session_id,
        )
    except Exception:
        if ephemeral:
            config._store.sessions.update_status(session_id, SessionStatus.ERROR)
        raise
