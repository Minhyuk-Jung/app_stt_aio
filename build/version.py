"""Build-time version constants (C16 plan §6.1)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        raise RuntimeError("version not found in pyproject.toml")
    return match.group(1)


VERSION = read_pyproject_version()
PRODUCT_NAME = "STT-AIO"
PUBLISHER = "STT-AIO"
EXE_NAME = "STT-AIO.exe"
# C16/C18: Whisper models are downloaded at runtime, not bundled in the installer.
BUNDLE_MODELS = False
