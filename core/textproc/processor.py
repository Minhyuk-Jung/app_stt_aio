"""TextProcessor orchestration (C17)."""

from __future__ import annotations

import logging
from typing import Callable

from core.store.models import DictionaryType
from core.store.repos.dictionary_repo import DictionaryRepo
from core.textproc.dictionary import apply_dictionary
from core.textproc.normalize_ko import apply_ko_surface_rules, basic_normalize
from core.textproc.snippets import expand_snippets
from core.textproc.types import ProcCtx, ProcOptions, ProcResult

logger = logging.getLogger(__name__)

OptionsProvider = Callable[[], ProcOptions]


class TextProcessor:
    """Deterministic post-STT text processing."""

    def __init__(
        self,
        dictionary_repo: DictionaryRepo,
        options_provider: OptionsProvider | None = None,
    ) -> None:
        self._dictionary_repo = dictionary_repo
        self._options_provider = options_provider or (lambda: ProcOptions())
        self._vocab_cache: list | None = None
        self._snippet_cache: list | None = None

    def invalidate_cache(self) -> None:
        self._vocab_cache = None
        self._snippet_cache = None

    def process(self, text: str, context: ProcCtx | None = None) -> ProcResult:
        ctx = context or ProcCtx()
        options = self._resolve_options(ctx)
        applied: list[str] = []

        def mark(rule: str) -> None:
            applied.append(rule)

        if not text:
            return ProcResult(text="", applied=tuple())

        result = text
        if options.normalize:
            result = basic_normalize(result)
            if result != text:
                mark("normalize:basic")

        if options.dictionary:
            try:
                vocab = self._load_vocab(ctx.target_app)
                before = result
                result = self.apply_dictionary(result, vocab, on_applied=mark)
                if result == before and vocab:
                    pass
            except Exception as exc:  # noqa: BLE001
                logger.warning("Dictionary step disabled due to load error: %s", exc)

        if options.snippets:
            try:
                snippets = self._load_snippets(ctx.target_app)
                result = self.expand_snippets(result, snippets, on_applied=mark)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Snippet step disabled due to load error: %s", exc)

        if options.normalize and (
            options.punctuation_spacing or options.number_spacing
        ):
            before = result
            result = apply_ko_surface_rules(
                result,
                punctuation_spacing=options.punctuation_spacing,
                number_spacing=options.number_spacing,
            )
            if result != before:
                if options.punctuation_spacing:
                    mark("normalize:ko_punct")
                if options.number_spacing:
                    mark("normalize:ko_number")

        return ProcResult(text=result, applied=tuple(applied))

    def _resolve_options(self, ctx: ProcCtx) -> ProcOptions:
        """Prefer explicit ProcCtx options; fall back to injected provider."""
        if ctx.options != ProcOptions():
            return ctx.options
        return self._options_provider()

    def normalize_ko(
        self,
        text: str,
        *,
        punctuation_spacing: bool = False,
        number_spacing: bool = False,
    ) -> str:
        from core.textproc.normalize_ko import normalize_ko

        return normalize_ko(
            text,
            punctuation_spacing=punctuation_spacing,
            number_spacing=number_spacing,
        )

    def apply_dictionary(
        self,
        text: str,
        entries: list | None = None,
        *,
        on_applied: Callable[[str], None] | None = None,
    ) -> str:
        vocab = entries if entries is not None else self._load_vocab()
        return apply_dictionary(text, vocab, on_applied=on_applied)

    def expand_snippets(
        self,
        text: str,
        entries: list | None = None,
        *,
        on_applied: Callable[[str], None] | None = None,
    ) -> str:
        snippets = entries if entries is not None else self._load_snippets()
        return expand_snippets(text, snippets, on_applied=on_applied)

    def _filter_by_target_app(self, entries: list, target_app: str | None) -> list:
        if not target_app:
            return [entry for entry in entries if not getattr(entry, "target_app", None)]
        return [
            entry
            for entry in entries
            if getattr(entry, "target_app", None) in (None, "", target_app)
        ]

    def _load_vocab(self, target_app: str | None = None) -> list:
        if self._vocab_cache is None:
            self._vocab_cache = self._dictionary_repo.list_enabled(DictionaryType.VOCAB)
        return self._filter_by_target_app(self._vocab_cache, target_app)

    def _load_snippets(self, target_app: str | None = None) -> list:
        if self._snippet_cache is None:
            self._snippet_cache = self._dictionary_repo.list_enabled(DictionaryType.SNIPPET)
        return self._filter_by_target_app(self._snippet_cache, target_app)
