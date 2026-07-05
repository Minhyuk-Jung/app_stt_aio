"""Domain models for Store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SessionSource(str, Enum):
    BATCH = "batch"
    REALTIME = "realtime"
    REMOTE = "remote"


class SessionStatus(str, Enum):
    RECORDING = "recording"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    CANCELED = "canceled"


@dataclass
class Session:
    id: str
    created_at: datetime
    source: SessionSource
    mode_id: str | None
    audio_path: str | None
    status: SessionStatus


@dataclass
class Setting:
    key: str
    value: str
    updated_at: datetime


@dataclass
class Artifact:
    id: str
    session_id: str
    stage: int
    text: str
    provider: str | None
    prompt_snapshot: str | None
    created_at: datetime


class DictionaryType(str, Enum):
    VOCAB = "vocab"
    SNIPPET = "snippet"


@dataclass
class DictionaryEntry:
    id: str
    term: str
    replacement: str
    type: DictionaryType
    enabled: bool
    updated_at: datetime
    target_app: str | None = None


@dataclass
class Mode:
    id: str
    name: str
    target_stage: int
    inject_stage: int
    correction_prompt: str
    report_prompt: str
    stt_provider: str | None
    llm_provider: str | None
    is_default: bool
    is_builtin: bool
    enabled: bool
    updated_at: datetime
