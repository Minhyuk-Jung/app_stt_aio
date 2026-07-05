"""Workbench controller — Qt-free bridge to C6 (C13)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from core.export import (
    ExportPayload,
    ExportResult,
    ExportTarget,
    available_templates,
    build_export_filename,
    ensure_unique_path,
    export,
)
from core.pipeline.types import PipelineStatus
from core.store.models import Artifact, Session, SessionStatus

if TYPE_CHECKING:
    from app.config.config import Config
    from app.session.session_manager import SessionManager
    from core.pipeline.pipeline import Pipeline

logger = logging.getLogger(__name__)

SessionStateCallback = Callable[[str, SessionStatus], None]
StageCompletedCallback = Callable[[str, int], None]

DEFAULT_PAGE_SIZE = 50


@dataclass(frozen=True)
class SessionSummary:
    id: str
    created_at: datetime
    status: SessionStatus
    source: str
    mode_name: str
    preview_text: str


@dataclass(frozen=True)
class SessionDetail:
    session: Session
    mode_name: str
    artifacts: dict[int, Artifact]


@dataclass(frozen=True)
class ReprocessResult:
    success: bool
    error: str | None = None
    stages_completed: tuple[int, ...] = ()


class WorkbenchNotImplementedError(NotImplementedError):
    """Raised for P3 workbench features (reprocess, etc.)."""


class WorkbenchController:
    """Plan section 3 actions without Qt dependencies."""

    def __init__(
        self,
        config: Config,
        *,
        session_manager: SessionManager | None = None,
    ) -> None:
        self._config = config
        self._session_manager = session_manager
        self._session_listeners: list[SessionStateCallback] = []
        self._stage_listeners: list[StageCompletedCallback] = []
        self._pipeline_bound = False
        if session_manager is not None:
            session_manager.on_session_state(self._on_session_state)

    @property
    def config(self) -> Config:
        return self._config

    def bind_pipeline(self, pipeline: Pipeline) -> None:
        """Subscribe to C4 stage completion for live workbench refresh."""
        if self._pipeline_bound:
            return
        pipeline.on_stage_completed(self._on_pipeline_stage_completed)
        self._pipeline_bound = True

    def on_session_state(self, callback: SessionStateCallback) -> None:
        self._session_listeners.append(callback)

    def on_stage_completed(self, callback: StageCompletedCallback) -> None:
        self._stage_listeners.append(callback)

    def list_sessions(
        self,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        status: SessionStatus | None = None,
        mode_id: str | None = None,
        query: str | None = None,
    ) -> list[SessionSummary]:
        store = self._config._store
        normalized = (query or "").strip()
        if normalized:
            sessions = store.sessions.search(
                normalized,
                limit=limit,
                offset=offset,
                status=status,
                mode_id=mode_id,
            )
        else:
            sessions = store.sessions.list(
                limit=limit,
                offset=offset,
                status=status,
                mode_id=mode_id,
            )
        return [self._to_summary(session) for session in sessions]

    def count_sessions(
        self,
        *,
        status: SessionStatus | None = None,
        mode_id: str | None = None,
        query: str | None = None,
    ) -> int:
        store = self._config._store
        normalized = (query or "").strip()
        if normalized:
            return store.sessions.search_count(
                normalized,
                status=status,
                mode_id=mode_id,
            )
        return store.sessions.count(status=status, mode_id=mode_id)

    def get_focus_session_id(self) -> str | None:
        """Prefer active recording/processing session, else latest."""
        if self._session_manager is not None:
            if self._session_manager.processing_session_id:
                return self._session_manager.processing_session_id
            if self._session_manager.recording_session_id:
                return self._session_manager.recording_session_id
        for status in (SessionStatus.PROCESSING, SessionStatus.RECORDING):
            active = self.list_sessions(limit=1, status=status)
            if active:
                return active[0].id
        sessions = self.list_sessions(limit=1)
        return sessions[0].id if sessions else None

    def get_session_detail(self, session_id: str) -> SessionDetail | None:
        store = self._config._store
        session = store.sessions.get(session_id)
        if session is None:
            return None
        artifacts: dict[int, Artifact] = {}
        for stage in (1, 2, 3):
            artifact = store.artifacts.latest_by_stage(session_id, stage)
            if artifact is not None:
                artifacts[stage] = artifact
        return SessionDetail(
            session=session,
            mode_name=self._resolve_mode_name(session.mode_id),
            artifacts=artifacts,
        )

    def update_artifact_text(self, artifact_id: str, text: str) -> Artifact | None:
        return self._config._store.artifacts.update_text(artifact_id, text)

    def request_reprocess(
        self,
        session_id: str,
        from_stage: int,
        *,
        seed_text: str | None = None,
    ) -> ReprocessResult:
        """Run C4 reprocess for workbench (stage 2 or 3)."""
        if from_stage not in (2, 3):
            return ReprocessResult(
                success=False,
                error="재가공은 2차 또는 3차부터만 지원합니다.",
            )
        detail = self.get_session_detail(session_id)
        if detail is None:
            return ReprocessResult(success=False, error="세션을 찾을 수 없습니다.")
        if from_stage >= 2 and 1 not in detail.artifacts:
            return ReprocessResult(success=False, error="1차 산출물이 없습니다.")
        if from_stage >= 3 and 2 not in detail.artifacts:
            return ReprocessResult(success=False, error="2차 산출물이 없습니다.")

        pipeline = self._config._pipeline
        if pipeline is None:
            pipeline = self._config.bind_pipeline()

        effective_seed = seed_text
        if effective_seed is None and from_stage >= 2:
            effective_seed = detail.artifacts[1].text

        run = pipeline.reprocess(
            session_id,
            from_stage,
            seed_text=effective_seed,
        )
        if run.status is PipelineStatus.ERROR:
            return ReprocessResult(success=False, error=run.error or "재가공 실패")
        if run.status is PipelineStatus.CANCELED:
            return ReprocessResult(success=False, error="재가공이 취소되었습니다.")
        completed = tuple(sorted(run.artifacts.keys()))
        return ReprocessResult(success=True, stages_completed=completed)

    def request_export(
        self,
        session_id: str,
        stage: int,
        dest_path: Path,
        *,
        export_format: str = "txt",
        text_override: str | None = None,
        template: str | None = None,
        include_meta: bool = False,
    ) -> ExportResult:
        target = ExportTarget(
            session_id=session_id,
            stages=(stage,),
            template=template,
            include_meta=include_meta,
        )
        return self.request_export_target(
            target,
            dest_path,
            export_format=export_format,
            text_overrides={stage: text_override} if text_override is not None else None,
        )

    def request_export_target(
        self,
        target: ExportTarget,
        dest_path: Path,
        *,
        export_format: str = "txt",
        text_overrides: dict[int, str] | None = None,
    ) -> ExportResult:
        detail = self.get_session_detail(target.session_id)
        if detail is None:
            return ExportResult(
                path=dest_path,
                format=export_format,
                success=False,
                error="session not found",
                suggestion="목록을 새로고침한 뒤 다시 시도하세요.",
            )

        overrides = text_overrides or {}
        stage_text: dict[int, str] = {}
        providers: dict[int, str | None] = {}
        for stage in target.stages:
            if stage in overrides:
                stage_text[stage] = overrides[stage]
                artifact = detail.artifacts.get(stage)
                providers[stage] = artifact.provider if artifact else None
                continue
            artifact = detail.artifacts.get(stage)
            if artifact is None:
                return ExportResult(
                    path=dest_path,
                    format=export_format,
                    success=False,
                    error=f"stage {stage} artifact not found",
                    suggestion="txt, md, docx 형식으로 다른 stage를 선택하세요.",
                )
            stage_text[stage] = artifact.text
            providers[stage] = artifact.provider

        if export_format.lower() == "docx" and target.template is None:
            target = ExportTarget(
                session_id=target.session_id,
                stages=target.stages,
                include_meta=target.include_meta,
                template=self._default_docx_template(),
            )

        payload = ExportPayload(
            session_id=target.session_id,
            mode_name=detail.mode_name,
            created_at=detail.session.created_at,
            stages=stage_text,
            providers=providers,
        )
        return export(target, dest_path, export_format, payload)

    def _default_docx_template(self) -> str:
        return str(self._config.get("export.default_docx_template"))

    def resolve_default_export_path(
        self,
        session_id: str,
        stage: int | str,
        *,
        export_format: str = "txt",
        unique: bool = True,
    ) -> Path:
        export_dir = self._config.resolve_export_dir()
        pattern = str(self._config.get("export.filename_pattern"))
        mode_name = "session"
        when = None
        detail = self.get_session_detail(session_id)
        if detail is not None:
            mode_name = detail.mode_name
            when = detail.session.created_at
        filename = build_export_filename(
            pattern,
            mode_name=mode_name,
            stage=stage,
            export_format=export_format,
            when=when,
        )
        path = export_dir / filename
        if unique:
            return ensure_unique_path(path)
        return path

    def list_export_templates(self, export_format: str) -> list[tuple[str, str]]:
        return [(info.id, info.name) for info in available_templates(export_format)]

    def default_docx_template(self) -> str:
        return self._default_docx_template()

    def list_enabled_modes(self) -> list[tuple[str, str]]:
        return [
            (mode.id, mode.name)
            for mode in self._config.mode_manager.list_modes(enabled_only=True)
        ]

    def _to_summary(self, session: Session) -> SessionSummary:
        preview = ""
        artifact = self._config._store.artifacts.latest_by_stage(session.id, 1)
        if artifact is not None:
            preview = artifact.text.replace("\n", " ").strip()
            if len(preview) > 80:
                preview = preview[:77] + "..."
        return SessionSummary(
            id=session.id,
            created_at=session.created_at,
            status=session.status,
            source=session.source.value,
            mode_name=self._resolve_mode_name(session.mode_id),
            preview_text=preview or "(산출물 없음)",
        )

    def _resolve_mode_name(self, mode_id: str | None) -> str:
        if not mode_id:
            return "기본"
        try:
            return self._config.mode_manager.get_mode(mode_id).name
        except Exception:  # noqa: BLE001
            return mode_id

    def _on_session_state(self, session_id: str, status: SessionStatus) -> None:
        for callback in self._session_listeners:
            try:
                callback(session_id, status)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Workbench session listener failed: %s", exc)
        if status is SessionStatus.DONE:
            self._emit_stage_completed(session_id, 1)

    def _on_pipeline_stage_completed(self, stage: int, artifact) -> None:
        self._emit_stage_completed(artifact.session_id, stage)

    def _emit_stage_completed(self, session_id: str, stage: int) -> None:
        for callback in self._stage_listeners:
            try:
                callback(session_id, stage)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Workbench stage listener failed: %s", exc)
