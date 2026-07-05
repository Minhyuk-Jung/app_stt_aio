"""Pipeline stage executors (C4)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.llm.types import LLMRequest
from core.pipeline.types import StageArtifact
from core.stt.types import STTResult
from core.textproc.types import ProcCtx

if TYPE_CHECKING:
    from app.config.config import Config
    from core.audio.format import AudioBuffer

logger = logging.getLogger(__name__)


def post_process_stage1_text(config: Config, text: str) -> str:
    """Deterministic stage1 post-processing via C17 TextProcessor."""
    if config._text_processor is None:
        config.bind_text_processor()
    result = config.text_processor.process(
        text,
        ProcCtx(stage=1, source="stt", options=config.get_proc_options()),
    )
    if result.applied:
        logger.debug("textproc stage1 applied rules: %s", ", ".join(result.applied))
    return result.text


def run_stage1(
    config: Config,
    audio: AudioBuffer,
    session_id: str,
) -> tuple[STTResult, StageArtifact]:
    """Execute STT for stage1 and build artifact payload."""
    if config._stt_session is None:
        config.bind_stt_session()

    stt_result = config.stt_session.transcribe_segment(
        audio,
        config.get_stt_options(),
    )
    processed_text = post_process_stage1_text(config, stt_result.text)
    artifact = StageArtifact(
        session_id=session_id,
        stage=1,
        text=processed_text,
        language=stt_result.language,
        provider=stt_result.provider_id or None,
    )
    return stt_result, artifact


def _resolve_mode_id(config: Config, session_id: str, mode_id: str | None) -> str | None:
    if mode_id is not None:
        return mode_id
    stored = config._store.sessions.get(session_id)
    return stored.mode_id if stored is not None else None


def _passthrough_llm_artifact(
    session_id: str,
    stage: int,
    source_text: str,
    *,
    language: str,
) -> StageArtifact:
    """Skip LLM when there is no user text to process (C3 edge case)."""
    return StageArtifact(
        session_id=session_id,
        stage=stage,
        text=source_text,
        language=language,
        provider=None,
    )


def run_stage2(
    config: Config,
    session_id: str,
    source_text: str,
    *,
    language: str = "ko",
    mode_id: str | None = None,
) -> tuple[StageArtifact, str]:
    """Execute LLM correction (stage2) using C7 prompts."""
    if config._llm_session is None:
        config.bind_llm_session()

    resolved_mode_id = _resolve_mode_id(config, session_id, mode_id)
    mode = config.mode_manager.resolve_mode(resolved_mode_id)
    prompt = config.mode_manager.get_prompt(mode, 2)

    if not source_text.strip():
        return _passthrough_llm_artifact(
            session_id, 2, source_text, language=language
        ), prompt.system_prompt

    provider_id = config.mode_manager.resolve_llm_provider(mode, config.get("llm.provider"))
    request = LLMRequest(
        system_prompt=prompt.system_prompt,
        user_text=source_text,
        mode_id=mode.id,
        params=config.get_llm_params(),
    )
    result = config.llm_session.complete(request, provider_id=provider_id)
    artifact = StageArtifact(
        session_id=session_id,
        stage=2,
        text=result.text,
        language=language,
        provider=result.provider_id,
    )
    return artifact, prompt.system_prompt


def run_stage2_stream(
    config: Config,
    session_id: str,
    source_text: str,
    *,
    language: str = "ko",
    mode_id: str | None = None,
):
    """Stream LLM correction tokens (C3); yields text deltas."""
    if config._llm_session is None:
        config.bind_llm_session()

    resolved_mode_id = _resolve_mode_id(config, session_id, mode_id)
    mode = config.mode_manager.resolve_mode(resolved_mode_id)
    prompt = config.mode_manager.get_prompt(mode, 2)
    if not source_text.strip():
        yield ""
        return

    provider_id = config.mode_manager.resolve_llm_provider(mode, config.get("llm.provider"))
    request = LLMRequest(
        system_prompt=prompt.system_prompt,
        user_text=source_text,
        mode_id=mode.id,
        params=config.get_llm_params(),
    )
    parts: list[str] = []
    for delta in config.llm_session.stream(request, provider_id=provider_id):
        parts.append(delta.text)
        yield delta.text


def run_stage3(
    config: Config,
    session_id: str,
    source_text: str,
    *,
    language: str = "ko",
    mode_id: str | None = None,
) -> tuple[StageArtifact, str]:
    """Execute LLM report generation (stage3) using C7 prompts."""
    if config._llm_session is None:
        config.bind_llm_session()

    resolved_mode_id = _resolve_mode_id(config, session_id, mode_id)
    mode = config.mode_manager.resolve_mode(resolved_mode_id)
    prompt = config.mode_manager.get_prompt(mode, 3)

    if not source_text.strip():
        return _passthrough_llm_artifact(
            session_id, 3, source_text, language=language
        ), prompt.system_prompt

    provider_id = config.mode_manager.resolve_llm_provider(mode, config.get("llm.provider"))
    request = LLMRequest(
        system_prompt=prompt.system_prompt,
        user_text=source_text,
        mode_id=mode.id,
        params=config.get_llm_params(),
    )
    result = config.llm_session.complete(request, provider_id=provider_id)
    artifact = StageArtifact(
        session_id=session_id,
        stage=3,
        text=result.text,
        language=language,
        provider=result.provider_id,
    )
    return artifact, prompt.system_prompt
