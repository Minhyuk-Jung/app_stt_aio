"""Unit tests for NFR bench helpers (P5)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]


def _load_nfr_bench():
    spec = importlib.util.spec_from_file_location(
        "nfr_bench_mod",
        ROOT / "scripts" / "bench" / "nfr_bench.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["nfr_bench_mod"] = module
    spec.loader.exec_module(module)
    return module


def test_nfr_targets_file_exists() -> None:
    path = ROOT / "scripts" / "bench" / "nfr_targets.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["cold_start_warmup_ms"] == 3000
    assert payload["idle_cpu_percent"] == 1.0
    assert payload["packaged_startup_sec"] == 3.0
    assert payload["realtime_target_ms"] == 1000
    assert payload["idle_memory_mb_max"] == 500


def test_summarize_passes_when_sections_ok() -> None:
    nfr = _load_nfr_bench()
    report = {
        "cold_start": {
            "status": "ok",
            "warmup_pass": True,
            "transcribe_pass": True,
        },
        "app_import": {"status": "ok", "pass": True},
        "idle_cpu": {"status": "skip"},
    }
    assert nfr.summarize(report) is True


def test_summarize_fails_on_error() -> None:
    nfr = _load_nfr_bench()
    report = {
        "cold_start": {"status": "error", "reason": "boom"},
        "app_import": {"status": "ok", "pass": True},
        "idle_cpu": {"status": "skip"},
    }
    assert nfr.summarize(report) is False


def test_bench_app_import_reports_elapsed() -> None:
    nfr = _load_nfr_bench()
    with patch.object(nfr.time, "perf_counter", side_effect=[0.0, 0.5]):
        with patch.object(nfr, "import_module") as mock_import:
            result = nfr.bench_app_import(targets=nfr.load_targets())
    assert result["status"] == "ok"
    assert result["import_ms"] == 500.0
    assert mock_import.call_count == 3


def test_find_packaged_exe_returns_none_when_missing(tmp_path: Path) -> None:
    nfr = _load_nfr_bench()
    assert nfr.find_packaged_exe(tmp_path) is None


def test_find_packaged_exe_returns_path_when_present(tmp_path: Path) -> None:
    nfr = _load_nfr_bench()
    exe = tmp_path / "dist" / "STT-AIO" / "STT-AIO.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    assert nfr.find_packaged_exe(tmp_path) == exe


def test_bench_idle_cpu_packaged_skips_missing_exe(tmp_path: Path) -> None:
    nfr = _load_nfr_bench()
    missing = tmp_path / "missing.exe"
    result = nfr.bench_idle_cpu_packaged(missing, targets=nfr.load_targets())
    assert result["status"] == "skip"


def test_bench_idle_cpu_packaged_samples_process_tree(tmp_path: Path) -> None:
    nfr = _load_nfr_bench()
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"MZ")

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.pid = 4242

    mock_ps_proc = MagicMock()
    mock_ps_proc.pid = 4242
    mock_ps_proc.children.return_value = []

    with patch("subprocess.Popen", return_value=mock_proc):
        with patch.object(nfr.time, "sleep"):
            with patch.object(nfr, "_sample_process_tree_cpu", return_value=0.25):
                with patch.object(nfr, "_sample_process_tree_memory_mb", return_value=120.0):
                    with patch("psutil.Process", return_value=mock_ps_proc):
                        result = nfr.bench_idle_cpu_packaged(exe, targets=nfr.load_targets())

    assert result["status"] == "ok"
    assert result["cpu_percent"] == 0.25
    assert result["memory_mb"] == 120.0
    assert result["pass"] is True
    mock_proc.terminate.assert_called_once()


def test_summarize_fails_when_packaged_expected_but_skipped() -> None:
    nfr = _load_nfr_bench()
    report = {
        "packaged_exe_expected": True,
        "cold_start": {"status": "skip"},
        "app_import": {"status": "skip"},
        "realtime_latency": {"status": "skip"},
        "idle_cpu": {"status": "skip"},
        "idle_cpu_packaged": {"status": "skip", "reason": "boom"},
    }
    assert nfr.summarize(report) is False


def test_summarize_passes_when_packaged_idle_ok() -> None:
    nfr = _load_nfr_bench()
    report = {
        "packaged_exe_expected": True,
        "cold_start": {"status": "skip"},
        "app_import": {"status": "skip"},
        "realtime_latency": {"status": "skip"},
        "idle_cpu": {"status": "skip"},
        "idle_cpu_packaged": {"status": "ok", "pass": True},
    }
    assert nfr.summarize(report) is True
