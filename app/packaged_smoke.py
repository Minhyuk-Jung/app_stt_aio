"""Headless smoke checks for PyInstaller builds (no GUI, no user).

Simulates frozen-app conditions (stderr=None) and verifies critical paths
that previously only failed on installed builds.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


def run_packaged_smoke() -> int:
    """Return 0 when packaged-critical paths pass."""
    errors: list[str] = []

    if not _check_download_with_none_stderr():
        errors.append("download_with_none_stderr")

    if errors:
        print("packaged_smoke FAIL: " + ", ".join(errors), file=sys.stdout)
        return 1

    print("packaged_smoke_ok", file=sys.stdout)
    return 0


def _check_download_with_none_stderr() -> bool:
    """Regression: tqdm must not crash when stderr is None (windowed exe)."""
    from core.models.downloader import download_whisper_model

    original_stderr = sys.stderr
    sys.stderr = None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "tiny"
            progress: list[tuple[int, int, str]] = []

            def on_progress(downloaded: int, total: int, state: str) -> None:
                progress.append((downloaded, total, state))

            def fake_snapshot(**kwargs):
                tqdm_class = kwargs.get("tqdm_class")
                if tqdm_class is None:
                    raise AssertionError("expected tqdm_class")
                bar = tqdm_class(total=1024 * 1024)
                bar.update(1024 * 1024)
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "model.bin").write_bytes(b"ok")
                return str(dest)

            with patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot):
                download_whisper_model(
                    "tiny",
                    dest,
                    on_progress=on_progress,
                )
            return any(p[2] == "downloading" for p in progress) and (dest / "model.bin").is_file()
    except Exception as exc:  # noqa: BLE001
        print(f"packaged_smoke download error: {exc}", file=sys.stdout)
        return False
    finally:
        sys.stderr = original_stderr
