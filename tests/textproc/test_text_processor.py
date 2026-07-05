"""Tests for C17 TextProcessor."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Config
from core.audio.format import AudioBuffer
from core.pipeline.stages import post_process_stage1_text, run_stage1
from core.store import Store
from core.store.models import DictionaryType
from core.stt.types import STTResult
from core.textproc import ProcCtx, ProcOptions, TextProcessor
from core.textproc.normalize_ko import apply_ko_surface_rules, basic_normalize, normalize_ko
from core.textproc.dictionary import apply_dictionary
from core.textproc.snippets import normalize_snippet_triggers


@pytest.fixture
def processor_env(tmp_path: Path):
    store = Store(tmp_path / "textproc.db", migrate_backup=False)
    processor = TextProcessor(store.dictionaries)
    yield store, processor
    store.close()


def test_basic_normalize_trims_and_collapses_spaces() -> None:
    assert basic_normalize("  hello   world  ") == "hello world"
    assert basic_normalize("a\n\n  b") == "a\n\n b"


def test_normalize_ko_punctuation_spacing_optional() -> None:
    assert normalize_ko("안녕 , 세계") == "안녕 , 세계"
    assert normalize_ko("안녕 , 세계", punctuation_spacing=True) == "안녕, 세계"


def test_normalize_ko_number_spacing_optional() -> None:
    assert normalize_ko("가격 10000 원") == "가격 10000 원"
    assert normalize_ko("가격 10000 원", number_spacing=True) == "가격 10000원"


def test_apply_ko_surface_rules_number_only() -> None:
    assert apply_ko_surface_rules("10 원", number_spacing=True) == "10원"


def test_normalize_snippet_triggers_maps_stt_variants() -> None:
    assert normalize_snippet_triggers("슬래시 sig") == "/sig"
    assert normalize_snippet_triggers("슬러시sig") == "/sig"


def test_apply_dictionary_longest_first(processor_env) -> None:
    store, processor = processor_env
    store.dictionaries.create(
        term="GPT",
        replacement="지피티",
        entry_type=DictionaryType.VOCAB,
    )
    store.dictionaries.create(
        term="ChatGPT",
        replacement="챗지피티",
        entry_type=DictionaryType.VOCAB,
    )
    processor.invalidate_cache()

    result = processor.apply_dictionary("ChatGPT is great")
    assert result == "챗지피티 is great"


def test_apply_dictionary_case_insensitive_latin(processor_env) -> None:
    store, processor = processor_env
    store.dictionaries.create(
        term="gpt",
        replacement="GPT",
        entry_type=DictionaryType.VOCAB,
    )
    processor.invalidate_cache()
    assert processor.apply_dictionary("chatgpt and Gpt") == "chatgpt and GPT"


def test_apply_dictionary_word_boundary_latin(processor_env) -> None:
    store, processor = processor_env
    store.dictionaries.create(
        term="GPT",
        replacement="지피티",
        entry_type=DictionaryType.VOCAB,
    )
    processor.invalidate_cache()
    assert processor.apply_dictionary("ChatGPT rocks") == "ChatGPT rocks"
    assert processor.apply_dictionary("use GPT now") == "use 지피티 now"


def test_expand_snippets(processor_env) -> None:
    store, processor = processor_env
    store.dictionaries.create(
        term="/sig",
        replacement="감사합니다.\n홍길동",
        entry_type=DictionaryType.SNIPPET,
    )
    processor.invalidate_cache()

    result = processor.expand_snippets("메일 마무리 /sig")
    assert "감사합니다." in result
    assert "/sig" not in result


def test_overlapping_snippets_longest_first(processor_env) -> None:
    store, processor = processor_env
    store.dictionaries.create(
        term="/s",
        replacement="short",
        entry_type=DictionaryType.SNIPPET,
    )
    store.dictionaries.create(
        term="/sig",
        replacement="signature",
        entry_type=DictionaryType.SNIPPET,
    )
    processor.invalidate_cache()
    assert processor.expand_snippets("end /sig") == "end signature"


def test_dictionary_before_snippet_priority(processor_env) -> None:
    store, processor = processor_env
    store.dictionaries.create(
        term="/x",
        replacement="VOCAB",
        entry_type=DictionaryType.VOCAB,
    )
    store.dictionaries.create(
        term="/x",
        replacement="SNIPPET",
        entry_type=DictionaryType.SNIPPET,
    )
    processor.invalidate_cache()
    result = processor.process("/x tail", ProcCtx(options=ProcOptions(normalize=False)))
    assert result.text == "VOCAB tail"
    assert "vocab:/x" in result.applied
    assert "snippet:/x" not in result.applied


def test_process_pipeline_order(processor_env) -> None:
    store, processor = processor_env
    store.dictionaries.create(
        term="스티티",
        replacement="STT",
        entry_type=DictionaryType.VOCAB,
    )
    store.dictionaries.create(
        term="/thanks",
        replacement="감사합니다",
        entry_type=DictionaryType.SNIPPET,
    )
    processor.invalidate_cache()

    result = processor.process(
        "  스티티 로그 /thanks  ",
        ProcCtx(stage=1, options=ProcOptions(normalize=True, punctuation_spacing=False)),
    )
    assert result.text == "STT 로그 감사합니다"
    assert "normalize:basic" in result.applied
    assert "vocab:스티티" in result.applied
    assert "snippet:/thanks" in result.applied


def test_process_respects_toggles(processor_env) -> None:
    store, processor = processor_env
    store.dictionaries.create(
        term="foo",
        replacement="bar",
        entry_type=DictionaryType.VOCAB,
    )
    processor.invalidate_cache()

    off = processor.process(
        "  foo  ",
        ProcCtx(options=ProcOptions(normalize=False, dictionary=False)),
    )
    assert off.text == "  foo  "

    on = processor.process(
        "  foo  ",
        ProcCtx(options=ProcOptions(normalize=True, dictionary=True)),
    )
    assert on.text == "bar"


def test_process_empty_string(processor_env) -> None:
    _store, processor = processor_env
    result = processor.process("")
    assert result.text == ""
    assert result.applied == ()


def test_large_dictionary_apply(processor_env) -> None:
    store, processor = processor_env
    for index in range(200):
        store.dictionaries.create(
            term=f"term{index:03d}",
            replacement=f"r{index}",
            entry_type=DictionaryType.VOCAB,
        )
    processor.invalidate_cache()
    result = processor.apply_dictionary("prefix term199 suffix")
    assert result == "prefix r199 suffix"


def test_special_characters_in_terms(processor_env) -> None:
    store, processor = processor_env
    store.dictionaries.create(
        term="C++",
        replacement="씨플플",
        entry_type=DictionaryType.VOCAB,
    )
    processor.invalidate_cache()
    assert processor.apply_dictionary("learn C++ today") == "learn 씨플플 today"


def test_dictionary_load_failure_skips_step(processor_env, monkeypatch) -> None:
    _store, processor = processor_env

    def boom() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(processor, "_load_vocab", boom)
    result = processor.process(
        "  hello  ",
        ProcCtx(options=ProcOptions(normalize=True, dictionary=True)),
    )
    assert result.text == "hello"


def test_config_dictionary_api_invalidates_cache(tmp_path: Path) -> None:
    config = Config.open(tmp_path / "dict-api.db", migrate_backup=False)
    config.bind_text_processor()
    config.add_dictionary_entry(
        term="alpha",
        replacement="알파",
        entry_type=DictionaryType.VOCAB,
    )
    assert config.text_processor.apply_dictionary("alpha") == "알파"
    config.add_dictionary_entry(
        term="beta",
        replacement="베타",
        entry_type=DictionaryType.VOCAB,
    )
    assert config.text_processor.apply_dictionary("beta") == "베타"
    entries = config.list_dictionary_entries(enabled_only=True)
    to_delete = next(item for item in entries if item.term == "alpha")
    config.delete_dictionary_entry(to_delete.id)
    assert config.text_processor.apply_dictionary("alpha") == "alpha"
    config.close()


def test_dictionary_repo_crud(tmp_path: Path) -> None:
    from core.store.models import DictionaryEntry

    with Store(tmp_path / "dict.db", migrate_backup=False) as store:
        entry = store.dictionaries.create(
            term="클로드",
            replacement="Claude",
            entry_type=DictionaryType.VOCAB,
        )
        fetched = store.dictionaries.get(entry.id)
        assert fetched is not None
        assert fetched.term == "클로드"

        listed = store.dictionaries.list_enabled(DictionaryType.VOCAB)
        assert len(listed) == 1

        disabled = store.dictionaries.update(
            DictionaryEntry(
                id=entry.id,
                term=entry.term,
                replacement=entry.replacement,
                type=entry.type,
                enabled=False,
                updated_at=entry.updated_at,
            )
        )
        assert disabled.enabled is False
        assert store.dictionaries.list_enabled() == []

        assert store.dictionaries.delete(entry.id) is True


def test_post_process_stage1_via_config(tmp_path: Path) -> None:
    config = Config.open(tmp_path / "stage.db", migrate_backup=False)
    config.bind_text_processor()
    assert post_process_stage1_text(config, "  hello  ") == "hello"
    config.close()


def test_run_stage1_applies_text_processor(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    config = Config.open(tmp_path / "run1.db", migrate_backup=False)
    config.bind_stt_session()
    config._stt_session = MagicMock()
    config._stt_session.transcribe_segment.return_value = STTResult(
        text="  테스트  ",
        language="ko",
        provider_id="mock",
    )
    config.get_stt_options = MagicMock()

    _stt, artifact = run_stage1(config, AudioBuffer(pcm_bytes=b"\x00\x01"), "sid-1")
    assert artifact.text == "테스트"
    config.close()
