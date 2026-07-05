"""Tests for ModeManager."""

from __future__ import annotations

import pytest

from core.modes import ModeDeleteForbiddenError, ModeDraft, ModeManager, ModeNotFoundError, ModeValidationError
from core.store import Store


@pytest.fixture
def mode_manager(tmp_path):
    store = Store(tmp_path / "modes.db", migrate_backup=False)
    manager = ModeManager(store.modes)
    manager.seed_defaults()
    yield manager, store
    store.close()


def test_seed_defaults_is_idempotent(mode_manager) -> None:
    manager, _store = mode_manager
    first = manager.list_modes(enabled_only=False)
    second = manager.seed_defaults()

    assert len(first) == 4
    assert {mode.id for mode in first} == {
        "quick-dictation",
        "polish",
        "meeting",
        "report",
    }
    assert len(second) == 4
    assert manager._repo.count() == 4


def test_get_default_mode_is_quick_dictation(mode_manager) -> None:
    manager, _store = mode_manager
    default = manager.get_default_mode()
    assert default.id == "quick-dictation"
    assert default.is_default is True


def test_create_update_delete_custom_mode(mode_manager) -> None:
    manager, _store = mode_manager

    created = manager.create_mode(
        ModeDraft(name="메모", target_stage=1, inject_stage=1),
        mode_id="memo",
    )
    assert created.id == "memo"

    updated = manager.update_mode(
        "memo",
        ModeDraft(name="메모 수정", target_stage=1, inject_stage=0),
    )
    assert updated.name == "메모 수정"
    assert updated.inject_stage == 0

    manager.delete_mode("memo")
    with pytest.raises(ModeNotFoundError):
        manager.get_mode("memo")


def test_delete_builtin_mode_forbidden(mode_manager) -> None:
    manager, _store = mode_manager
    with pytest.raises(ModeDeleteForbiddenError):
        manager.delete_mode("quick-dictation")


def test_resolve_mode_falls_back_to_default(mode_manager) -> None:
    manager, _store = mode_manager
    resolved = manager.resolve_mode("missing-mode")
    assert resolved.id == "quick-dictation"


def test_get_prompt_for_stage_two_and_three(mode_manager) -> None:
    manager, _store = mode_manager
    polish = manager.get_mode("polish")

    stage2 = manager.get_prompt(polish, 2)
    stage3 = manager.get_prompt(polish, 3)

    assert "교정" in stage2.system_prompt
    assert stage3.system_prompt


def test_to_pipeline_mode_reflects_stages(mode_manager) -> None:
    manager, _store = mode_manager
    meeting = manager.get_mode("meeting")
    pipeline_mode = manager.to_pipeline_mode(meeting)
    assert pipeline_mode.target_stage == 3
    assert pipeline_mode.inject_stage == 0


def test_create_mode_rejects_duplicate_id(mode_manager) -> None:
    manager, _store = mode_manager
    with pytest.raises(ModeValidationError, match="already exists"):
        manager.create_mode(
            ModeDraft(name="중복", target_stage=1, inject_stage=1),
            mode_id="quick-dictation",
        )


def test_render_prompt_substitutes_text(mode_manager) -> None:
    manager, _store = mode_manager
    polish = manager.get_mode("polish")
    rendered = manager.render_prompt(polish, 2, "테스트 문장")
    assert "테스트 문장" in rendered
    assert "{{text}}" not in rendered


def test_restore_builtin_resets_edited_seed(mode_manager) -> None:
    manager, _store = mode_manager
    manager.update_mode(
        "polish",
        ModeDraft(name="변경됨", target_stage=2, inject_stage=2, correction_prompt="x"),
    )
    restored = manager.restore_builtin("polish")
    assert restored.name == "문장 다듬기"
    assert "교정" in restored.correction_prompt
