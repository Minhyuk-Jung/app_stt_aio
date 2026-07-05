"""Built-in default mode definitions (C7 seed)."""

from __future__ import annotations

from core.modes.types import ModeDraft

DEFAULT_CORRECTION_PROMPT = (
    "당신은 한국어 문장 교정 전문가입니다. "
    "사용자가 제공한 받아쓰기 원문을 자연스럽고 정확한 한국어 문장으로 다듬으세요. "
    "의미를 바꾸지 말고 띄어쓰기, 문장부호, 어색한 표현만 교정하세요.\n\n"
    "원문:\n{{text}}"
)

DEFAULT_REPORT_PROMPT = (
    "당신은 업무 문서 작성 전문가입니다. "
    "사용자가 제공한 내용을 바탕으로 구조화된 한국어 문서를 작성하세요. "
    "제목, 핵심 요약, 본문 항목을 명확히 구분하세요.\n\n"
    "입력:\n{{text}}"
)

BUILTIN_MODES: tuple[tuple[str, ModeDraft], ...] = (
    (
        "quick-dictation",
        ModeDraft(
            name="빠른 받아쓰기",
            target_stage=1,
            inject_stage=1,
            is_default=True,
        ),
    ),
    (
        "polish",
        ModeDraft(
            name="문장 다듬기",
            target_stage=2,
            inject_stage=2,
            correction_prompt=DEFAULT_CORRECTION_PROMPT,
        ),
    ),
    (
        "meeting",
        ModeDraft(
            name="회의록",
            target_stage=3,
            inject_stage=0,
            correction_prompt=DEFAULT_CORRECTION_PROMPT,
            report_prompt=DEFAULT_REPORT_PROMPT,
        ),
    ),
    (
        "report",
        ModeDraft(
            name="보고서",
            target_stage=3,
            inject_stage=0,
            correction_prompt=DEFAULT_CORRECTION_PROMPT,
            report_prompt=DEFAULT_REPORT_PROMPT,
        ),
    ),
)
