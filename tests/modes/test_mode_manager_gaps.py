"""Additional ModeManager coverage."""

from __future__ import annotations

import pytest

from core.modes import ModeDeleteForbiddenError, ModeDraft, ModeManager, ModeValidationError
from core.store import Store


@pytest.fixture
def mode_manager(tmp_path):
    store = Store(tmp_path / "modes_extra.db", migrate_backup=False)
    manager = ModeManager(store.modes)
    manager.seed_defaults()
    yield manager, store
    store.close()


def test_set_default_mode_updates_flag(mode_manager) -> None:
    manager, store = mode_manager
    updated = manager.set_default_mode("polish")
    assert updated.is_default is True
    assert manager.get_mode("quick-dictation").is_default is False
    assert store.modes.get_default().id == "polish"


def test_delete_default_mode_forbidden(mode_manager) -> None:
    manager, _store = mode_manager
    with pytest.raises(ModeDeleteForbiddenError):
        manager.delete_mode("quick-dictation")


def test_disable_default_mode_forbidden(mode_manager) -> None:
    manager, _store = mode_manager
    with pytest.raises(ModeDeleteForbiddenError):
        manager.disable_mode("quick-dictation")


def test_resolve_provider_override(mode_manager) -> None:
    manager, _store = mode_manager
    custom = manager.create_mode(
        ModeDraft(
            name="클라우드",
            target_stage=1,
            inject_stage=1,
            stt_provider="groq",
            llm_provider="openai",
        ),
        mode_id="cloud",
    )
    assert manager.resolve_stt_provider(custom, "faster_whisper_local") == "groq"
    assert manager.resolve_llm_provider(custom, "ollama") == "openai"

    polish = manager.get_mode("polish")
    assert manager.resolve_stt_provider(polish, "faster_whisper_local") == "faster_whisper_local"


def test_set_default_mode_rejects_disabled(mode_manager) -> None:
    manager, _store = mode_manager
    manager.disable_mode("polish")
    with pytest.raises(ModeValidationError):
        manager.set_default_mode("polish")
