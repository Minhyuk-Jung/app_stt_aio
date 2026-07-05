"""Pipeline orchestration engine (C4)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.pipeline.errors import PipelineCanceledError, PipelineNotImplementedError
from core.pipeline.event_bus import PipelineEventBus
from core.pipeline.inject import inject_stage_text
from core.pipeline.queue import PipelineQueue
from core.pipeline.mode_resolve import resolve_mode_for_session
from core.pipeline.stages import run_stage1, run_stage2, run_stage3
from core.pipeline.types import (
    DEFAULT_BATCH_MODE,
    PipelineInput,
    PipelineMode,
    PipelineRun,
    PipelineStatus,
    StageArtifact,
)
from core.store.models import SessionSource

if TYPE_CHECKING:
    from app.config.config import Config

logger = logging.getLogger(__name__)

CancelCheck = Callable[[], bool]


class Pipeline:
    """Batch pipeline: audio -> STT -> optional LLM stages -> store/inject."""

    def __init__(
        self,
        config: Config,
        *,
        queue: PipelineQueue | None = None,
        events: PipelineEventBus | None = None,
    ) -> None:
        self._config = config
        self._queue = queue or PipelineQueue()
        self._events = events or PipelineEventBus()

    def on_stage_started(self, callback) -> None:
        self._events.on_stage_started(callback)

    def on_stage_completed(self, callback) -> None:
        self._events.on_stage_completed(callback)

    def on_inject_requested(self, callback) -> None:
        self._events.on_inject_requested(callback)

    def on_pipeline_error(self, callback) -> None:
        self._events.on_pipeline_error(callback)

    def on_pipeline_finished(self, callback) -> None:
        self._events.on_pipeline_finished(callback)

    @property
    def queue(self) -> PipelineQueue:
        return self._queue

    def run(
        self,
        pipeline_input: PipelineInput,
        mode: PipelineMode | None = None,
        *,
        is_canceled: CancelCheck | None = None,
    ) -> PipelineRun:
        """Run batch path for configured mode stages."""
        active_mode = mode or DEFAULT_BATCH_MODE
        with self._queue.exclusive():
            return self._run_unlocked(
                pipeline_input,
                active_mode,
                is_canceled=is_canceled,
            )

    def reprocess(
        self,
        session_id: str,
        from_stage: int,
        mode: PipelineMode | None = None,
        *,
        seed_text: str | None = None,
        is_canceled: CancelCheck | None = None,
    ) -> PipelineRun:
        """Re-run stages from *from_stage* using stored or edited artifacts (C4 §6.4)."""
        if from_stage not in (1, 2, 3):
            raise ValueError("from_stage must be 1, 2, or 3")
        active_mode = mode or resolve_mode_for_session(self._config, session_id)
        if active_mode.target_stage < from_stage:
            active_mode = PipelineMode(
                id=active_mode.id,
                target_stage=from_stage,
                inject_stage=active_mode.inject_stage,
            )
        with self._queue.exclusive():
            return self._reprocess_unlocked(
                session_id,
                from_stage,
                active_mode,
                seed_text=seed_text,
                is_canceled=is_canceled or (lambda: False),
            )

    def _reprocess_unlocked(
        self,
        session_id: str,
        from_stage: int,
        mode: PipelineMode,
        *,
        seed_text: str | None,
        is_canceled: CancelCheck,
    ) -> PipelineRun:
        run = PipelineRun(session_id=session_id, status=PipelineStatus.RUNNING)
        store = self._config._store

        for stage in (1, 2, 3):
            stored = store.artifacts.latest_by_stage(session_id, stage)
            if stored is not None:
                run.artifacts[stage] = StageArtifact(
                    session_id=session_id,
                    stage=stage,
                    text=stored.text,
                    language="ko",
                    provider=stored.provider,
                )

        if from_stage == 1:
            return self._fail(
                run,
                stage=1,
                error=PipelineNotImplementedError(
                    "reprocess from stage 1 requires original audio; "
                    "re-run dictation instead"
                ),
            )

        if 1 not in run.artifacts:
            return self._fail(
                run,
                stage=from_stage,
                error=ValueError("stage 1 artifact is required for reprocess"),
            )

        if seed_text is not None:
            run.artifacts[1] = StageArtifact(
                session_id=session_id,
                stage=1,
                text=seed_text,
                language=run.artifacts[1].language,
                provider=run.artifacts[1].provider,
            )
            self._persist_stage_artifact(run.artifacts[1])

        language = run.artifacts[1].language

        try:
            if from_stage <= 2 and mode.target_stage >= 2:
                run = self._run_stage2(
                    run,
                    mode,
                    PipelineInput(source=SessionSource.BATCH, session_id=session_id),
                    is_canceled,
                )
                if run.status is not PipelineStatus.RUNNING:
                    return run

            if from_stage <= 3 and mode.target_stage >= 3:
                run = self._run_stage3(
                    run,
                    mode,
                    PipelineInput(source=SessionSource.BATCH, session_id=session_id),
                    is_canceled,
                )
                if run.status is not PipelineStatus.RUNNING:
                    return run

            run.status = PipelineStatus.FINISHED
            self._events.emit_pipeline_finished(run)
            return run
        except PipelineCanceledError:
            return self._cancel(run, stage=from_stage)
        except Exception as exc:
            return self._fail(run, stage=from_stage, error=exc)

    def _run_unlocked(
        self,
        pipeline_input: PipelineInput,
        mode: PipelineMode,
        *,
        is_canceled: CancelCheck | None,
    ) -> PipelineRun:
        session_id = pipeline_input.session_id
        if session_id is None:
            raise ValueError("pipeline_input.session_id is required")

        run = PipelineRun(session_id=session_id, status=PipelineStatus.RUNNING)
        canceled = is_canceled or (lambda: False)

        if pipeline_input.source is not SessionSource.BATCH:
            return self._fail(
                run,
                stage=0,
                error=PipelineNotImplementedError(
                    f"source {pipeline_input.source.value} is planned for a later phase"
                ),
            )

        if pipeline_input.audio is None:
            return self._fail(run, stage=1, error=ValueError("batch input requires audio"))

        if mode.target_stage < 1:
            return self._fail(run, stage=1, error=ValueError("target_stage must be >= 1"))

        try:
            self._events.emit_stage_started(1)
            if canceled():
                return self._cancel(run, stage=1)

            _stt_result, artifact = run_stage1(
                self._config,
                pipeline_input.audio,
                session_id,
            )
            self._persist_stage_artifact(artifact)
            run.artifacts[1] = artifact
            self._events.emit_stage_completed(1, artifact)

            if canceled():
                return self._cancel(run, stage=1)

            if mode.inject_stage == 1:
                self._inject_artifact(artifact, pipeline_input)
                run.artifacts[1] = artifact

            if mode.target_stage >= 2:
                run = self._run_stage2(run, mode, pipeline_input, canceled)
                if run.status is not PipelineStatus.RUNNING:
                    return run

            if mode.target_stage >= 3:
                run = self._run_stage3(run, mode, pipeline_input, canceled)
                if run.status is not PipelineStatus.RUNNING:
                    return run

            run.status = PipelineStatus.FINISHED
            self._events.emit_pipeline_finished(run)
            return run
        except PipelineCanceledError:
            return self._cancel(run, stage=1)
        except Exception as exc:
            return self._fail(run, stage=1, error=exc)

    def _run_stage2(
        self,
        run: PipelineRun,
        mode: PipelineMode,
        pipeline_input: PipelineInput,
        canceled: CancelCheck,
    ) -> PipelineRun:
        session_id = run.session_id

        self._events.emit_stage_started(2)
        if canceled():
            return self._cancel(run, stage=2)

        try:
            artifact2, snapshot = run_stage2(
                self._config,
                session_id,
                run.artifacts[1].text,
                language=run.artifacts[1].language,
            )
        except Exception as exc:
            return self._fail(run, stage=2, error=exc)

        self._persist_stage_artifact(artifact2, prompt_snapshot=snapshot)
        run.artifacts[2] = artifact2
        self._events.emit_stage_completed(2, artifact2)

        if canceled():
            return self._cancel(run, stage=2)

        if mode.inject_stage == 2:
            self._inject_artifact(artifact2, pipeline_input)
            run.artifacts[2] = artifact2

        return run

    def _run_stage3(
        self,
        run: PipelineRun,
        mode: PipelineMode,
        pipeline_input: PipelineInput,
        canceled: CancelCheck,
    ) -> PipelineRun:
        session_id = run.session_id

        self._events.emit_stage_started(3)
        if canceled():
            return self._cancel(run, stage=3)

        source_artifact = run.artifacts.get(2, run.artifacts[1])
        try:
            artifact3, snapshot = run_stage3(
                self._config,
                session_id,
                source_artifact.text,
                language=source_artifact.language,
            )
        except Exception as exc:
            return self._fail(run, stage=3, error=exc)

        self._persist_stage_artifact(artifact3, prompt_snapshot=snapshot)
        run.artifacts[3] = artifact3
        self._events.emit_stage_completed(3, artifact3)

        if canceled():
            return self._cancel(run, stage=3)

        if mode.inject_stage == 3:
            self._inject_artifact(artifact3, pipeline_input)
            run.artifacts[3] = artifact3

        return run

    def _inject_artifact(
        self,
        artifact: StageArtifact,
        pipeline_input: PipelineInput,
    ) -> None:
        inject_result = self._inject_text(
            artifact.text,
            press_enter=pipeline_input.press_enter,
            inject_method=pipeline_input.inject_method,
        )
        artifact.inject_result = inject_result
        if not inject_result.success and inject_result.error:
            from core.diagnostics import log_event

            log_event(
                logger,
                logging.WARNING,
                "pipeline inject failed",
                stage=artifact.stage,
                method=inject_result.method_used.value,
                text_len=len(artifact.text),
                error=inject_result.error,
            )
        self._events.emit_inject_requested(artifact)

    def _inject_text(
        self,
        text: str,
        *,
        press_enter: bool,
        inject_method: str | None = None,
    ):
        if not text.strip():
            from core.inject.types import InjectMethod, InjectResult

            return InjectResult(
                success=True,
                method_used=InjectMethod.UNICODE,
                chars_injected=0,
            )
        return inject_stage_text(
            self._config,
            text,
            press_enter=press_enter,
            inject_method=inject_method,
        )

    def _persist_stage_artifact(
        self,
        artifact: StageArtifact,
        *,
        prompt_snapshot: str | None = None,
    ) -> None:
        self._config._store.artifacts.add(
            artifact.session_id,
            artifact.stage,
            artifact.text,
            provider=artifact.provider,
            prompt_snapshot=prompt_snapshot,
        )

    def _cancel(self, run: PipelineRun, *, stage: int) -> PipelineRun:
        run.status = PipelineStatus.CANCELED
        run.error_stage = stage
        self._events.emit_pipeline_finished(run)
        return run

    def _fail(self, run: PipelineRun, *, stage: int, error: Exception) -> PipelineRun:
        run.status = PipelineStatus.ERROR
        run.error_stage = stage
        run.error = str(error)
        self._events.emit_pipeline_error(stage, error)
        self._events.emit_pipeline_finished(run)
        return run
