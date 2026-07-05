"""P0 spike script smoke tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _run_script(rel: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / rel), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_inject_ko_smoke_dry_run() -> None:
    result = _run_script("scripts/spike/inject_ko_smoke.py", "--dry-run")
    assert result.returncode == 0
    assert "encoding_roundtrip=ok" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Windows clipboard")
def test_inject_ko_smoke_verify_clipboard() -> None:
    result = _run_script("scripts/spike/inject_ko_smoke.py", "--verify-clipboard")
    assert result.returncode == 0
    assert "clipboard_roundtrip=ok" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Windows clipboard paste")
def test_inject_ko_smoke_verify_paste() -> None:
    result = _run_script("scripts/spike/inject_ko_smoke.py", "--verify-paste")
    assert result.returncode == 0
    assert "paste_path=ok" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Windows SendInput auto")
def test_inject_ko_smoke_auto() -> None:
    result = _run_script("scripts/spike/inject_ko_smoke.py", "--inject-auto")
    assert result.returncode == 0
    assert "inject_auto=ok" in result.stdout


def test_realtime_latency_runs() -> None:
    result = _run_script("scripts/bench/realtime_latency.py", "--model", "tiny")
    assert result.returncode in (0, 1)
    assert "status=" in result.stdout or "total_ms=" in result.stdout


def test_ollama_smoke_runs() -> None:
    result = _run_script("scripts/spike/ollama_smoke.py")
    assert result.returncode in (0, 1)
    assert "status=" in result.stdout


def test_vad_segment_bench_passes() -> None:
    result = _run_script("scripts/bench/vad_segment.py")
    assert result.returncode == 0
    assert "pass=True" in result.stdout


def test_tunnel_check_runs() -> None:
    result = _run_script("scripts/smoke/tunnel_check.py")
    assert result.returncode in (0, 1)
    assert "status=" in result.stdout
