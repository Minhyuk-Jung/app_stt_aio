"""Mode preset management (C7)."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

from core.modes.defaults import BUILTIN_MODES
from core.modes.errors import (
    ModeDeleteForbiddenError,
    ModeNotFoundError,
    ModeValidationError,
)
from core.modes.prompts import format_prompt
from core.modes.types import ModeDraft, PromptSpec
from core.modes.validation import normalize_prompt, validate_mode_draft
from core.pipeline.types import PipelineMode
from core.store.models import Mode
from core.store.repos.mode_repo import ModeRepo

logger = logging.getLogger(__name__)


class ModeManager:
    """CRUD and prompt resolution for pipeline modes."""

    def __init__(self, repo: ModeRepo) -> None:
        self._repo = repo

    def seed_defaults(self) -> list[Mode]:
        """Insert built-in modes when the table is empty (idempotent)."""
        if self._repo.count() > 0:
            return self.list_modes(enabled_only=False)

        created: list[Mode] = []
        now = datetime.now(timezone.utc)
        for mode_id, draft in BUILTIN_MODES:
            validated = validate_mode_draft(draft)
            mode = Mode(
                id=mode_id,
                name=validated.name,
                target_stage=validated.target_stage,
                inject_stage=validated.inject_stage,
                correction_prompt=validated.correction_prompt,
                report_prompt=validated.report_prompt,
                stt_provider=validated.stt_provider,
                llm_provider=validated.llm_provider,
                is_default=validated.is_default,
                is_builtin=True,
                enabled=validated.enabled,
                updated_at=now,
            )
            created.append(self._repo.create(mode))
        logger.info("Seeded %s default modes", len(created))
        return created

    def list_modes(self, *, enabled_only: bool = True) -> list[Mode]:
        return self._repo.list(enabled_only=enabled_only)

    def get_mode(self, mode_id: str) -> Mode:
        mode = self._repo.get(mode_id)
        if mode is None:
            raise ModeNotFoundError(mode_id)
        return mode

    def get_default_mode(self) -> Mode:
        mode = self._repo.get_default()
        if mode is None:
            raise ModeNotFoundError("default")
        return mode

    def resolve_mode(self, mode_id: str | None) -> Mode:
        if mode_id:
            mode = self._repo.get(mode_id)
            if mode is not None and mode.enabled:
                return mode
            logger.warning("Unknown or disabled mode %s; falling back to default", mode_id)
        return self.get_default_mode()

    def set_default_mode(self, mode_id: str) -> Mode:
        mode = self.get_mode(mode_id)
        if not mode.enabled:
            raise ModeValidationError(f"cannot set disabled mode as default: {mode_id}")
        return self.update_mode(
            mode_id,
            ModeDraft(
                name=mode.name,
                target_stage=mode.target_stage,
                inject_stage=mode.inject_stage,
                correction_prompt=mode.correction_prompt,
                report_prompt=mode.report_prompt,
                stt_provider=mode.stt_provider,
                llm_provider=mode.llm_provider,
                is_default=True,
                enabled=True,
            ),
        )

    def resolve_stt_provider(self, mode: Mode, default_provider: str) -> str:
        if mode.stt_provider:
            return mode.stt_provider
        return default_provider

    def resolve_llm_provider(self, mode: Mode, default_provider: str) -> str:
        if mode.llm_provider:
            return mode.llm_provider
        return default_provider

    def to_pipeline_mode(self, mode: Mode) -> PipelineMode:
        return PipelineMode(
            id=mode.id,
            target_stage=mode.target_stage,
            inject_stage=mode.inject_stage,
        )

    def get_prompt(self, mode: Mode, stage: int) -> PromptSpec:
        if stage == 2:
            return PromptSpec(system_prompt=normalize_prompt(2, mode.correction_prompt))
        if stage == 3:
            return PromptSpec(system_prompt=normalize_prompt(3, mode.report_prompt))
        return PromptSpec(system_prompt="")

    def render_prompt(self, mode: Mode, stage: int, text: str) -> str:
        """Return a stage prompt with user text substituted (C7/C3 bridge)."""
        spec = self.get_prompt(mode, stage)
        return format_prompt(spec.system_prompt, text)

    def create_mode(self, draft: ModeDraft, *, mode_id: str | None = None) -> Mode:
        validated = validate_mode_draft(draft)
        resolved_id = mode_id or self._new_mode_id(validated.name)
        if self._repo.get(resolved_id) is not None:
            raise ModeValidationError(f"mode id already exists: {resolved_id}")
        now = datetime.now(timezone.utc)
        mode = Mode(
            id=resolved_id,
            name=validated.name,
            target_stage=validated.target_stage,
            inject_stage=validated.inject_stage,
            correction_prompt=validated.correction_prompt,
            report_prompt=validated.report_prompt,
            stt_provider=validated.stt_provider,
            llm_provider=validated.llm_provider,
            is_default=validated.is_default,
            is_builtin=False,
            enabled=validated.enabled,
            updated_at=now,
        )
        return self._repo.create(mode)

    def update_mode(self, mode_id: str, draft: ModeDraft) -> Mode:
        existing = self.get_mode(mode_id)
        validated = validate_mode_draft(draft)
        updated = Mode(
            id=existing.id,
            name=validated.name,
            target_stage=validated.target_stage,
            inject_stage=validated.inject_stage,
            correction_prompt=validated.correction_prompt,
            report_prompt=validated.report_prompt,
            stt_provider=validated.stt_provider,
            llm_provider=validated.llm_provider,
            is_default=validated.is_default,
            is_builtin=existing.is_builtin,
            enabled=validated.enabled,
            updated_at=datetime.now(timezone.utc),
        )
        return self._repo.update(updated)

    def delete_mode(self, mode_id: str) -> None:
        mode = self.get_mode(mode_id)
        if mode.is_builtin or mode.is_default:
            raise ModeDeleteForbiddenError(
                f"cannot delete built-in or default mode: {mode_id}"
            )
        self._repo.delete(mode_id)

    def disable_mode(self, mode_id: str) -> Mode:
        mode = self.get_mode(mode_id)
        if mode.is_default:
            raise ModeDeleteForbiddenError(f"cannot disable default mode: {mode_id}")
        return self.update_mode(
            mode_id,
            ModeDraft(
                name=mode.name,
                target_stage=mode.target_stage,
                inject_stage=mode.inject_stage,
                correction_prompt=mode.correction_prompt,
                report_prompt=mode.report_prompt,
                stt_provider=mode.stt_provider,
                llm_provider=mode.llm_provider,
                is_default=False,
                enabled=False,
            ),
        )

    def restore_builtin(self, mode_id: str) -> Mode:
        for builtin_id, draft in BUILTIN_MODES:
            if builtin_id != mode_id:
                continue
            existing = self._repo.get(mode_id)
            if existing is None:
                raise ModeNotFoundError(mode_id)
            validated = validate_mode_draft(draft)
            restored = Mode(
                id=existing.id,
                name=validated.name,
                target_stage=validated.target_stage,
                inject_stage=validated.inject_stage,
                correction_prompt=validated.correction_prompt,
                report_prompt=validated.report_prompt,
                stt_provider=validated.stt_provider,
                llm_provider=validated.llm_provider,
                is_default=existing.is_default,
                is_builtin=True,
                enabled=True,
                updated_at=datetime.now(timezone.utc),
            )
            return self._repo.update(restored)
        raise ModeNotFoundError(mode_id)

    def _new_mode_id(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not slug:
            slug = "mode"
        candidate = slug
        suffix = 1
        while self._repo.get(candidate) is not None:
            candidate = f"{slug}-{suffix}"
            suffix += 1
            if suffix > 100:
                candidate = str(uuid.uuid4())
                break
        return candidate
