"""P5 NFR benchmarks (README §3, C16 §8).

Measures cold start, first transcribe, core import time, and idle CPU sample.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from importlib import import_module
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TARGETS_PATH = Path(__file__).resolve().parent / "nfr_targets.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.audio.capture_batch import generate_test_tone
from core.audio.format import AudioBuffer


def load_targets() -> dict[str, float]:
    if not TARGETS_PATH.is_file():
        return {
            "cold_start_warmup_ms": 3000,
            "first_transcribe_ms": 2000,
            "app_import_ms": 3000,
            "realtime_target_ms": 1000,
            "idle_cpu_percent": 1.0,
            "idle_cpu_sample_sec": 1.5,
            "packaged_startup_sec": 3.0,
            "idle_memory_mb_max": 500,
        }
    payload = json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
    return {key: float(value) for key, value in payload.items()}


def bench_cold_start(model_id: str, language: str, *, targets: dict[str, float]) -> dict[str, Any]:
    try:
        from core.stt.faster_whisper_local import FasterWhisperLocalProvider
    except ImportError as exc:
        return {"status": "skip", "reason": str(exc)}

    models_dir = Path(tempfile.mkdtemp(prefix="nfr_models_"))
    provider = FasterWhisperLocalProvider(
        models_dir=models_dir,
        model_id=model_id,
        device="cpu",
        compute_type="int8",
    )
    audio = AudioBuffer(pcm_bytes=generate_test_tone(duration_ms=800))

    started = time.perf_counter()
    try:
        provider.warmup()
        warmup_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        result = provider.transcribe(audio)
        first_transcribe_ms = (time.perf_counter() - started) * 1000
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": str(exc)}
    finally:
        provider.close()

    warmup_target = targets["cold_start_warmup_ms"]
    transcribe_target = targets["first_transcribe_ms"]
    return {
        "status": "ok",
        "model": model_id,
        "language": language,
        "warmup_ms": round(warmup_ms, 1),
        "first_transcribe_ms": round(first_transcribe_ms, 1),
        "text_len": len(result.text),
        "warmup_pass": warmup_ms < warmup_target,
        "transcribe_pass": first_transcribe_ms < transcribe_target,
        "warmup_target_ms": warmup_target,
        "transcribe_target_ms": transcribe_target,
    }


def bench_app_import(*, targets: dict[str, float]) -> dict[str, Any]:
    """Core import cost without starting Qt (README §3 app start proxy)."""
    started = time.perf_counter()
    try:
        import_module("app.config")
        import_module("core.pipeline.pipeline")
        import_module("core.store.store")
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": str(exc)}
    elapsed_ms = (time.perf_counter() - started) * 1000
    target_ms = targets["app_import_ms"]
    return {
        "status": "ok",
        "import_ms": round(elapsed_ms, 1),
        "target_ms": target_ms,
        "pass": elapsed_ms < target_ms,
    }


def find_packaged_exe(root: Path | None = None) -> Path | None:
    """Return dist/STT-AIO/STT-AIO.exe when the PyInstaller bundle exists."""
    base = root or ROOT
    candidate = base / "dist" / "STT-AIO" / "STT-AIO.exe"
    return candidate if candidate.is_file() else None


def _sample_process_tree_cpu(root_proc: Any, sample_sec: float) -> float:
    """Sample normalized CPU% for a process and its children (tray + helpers)."""
    import psutil

    logical = max(psutil.cpu_count(logical=True) or 1, 1)
    procs = [root_proc]
    try:
        procs.extend(root_proc.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    for proc in procs:
        try:
            proc.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(sample_sec)

    total = 0.0
    for proc in procs:
        try:
            total += proc.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total / logical


def _collect_process_tree(root_proc: Any) -> list[Any]:
    import psutil

    procs = [root_proc]
    try:
        procs.extend(root_proc.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return procs


def _sample_process_tree_memory_mb(root_proc: Any) -> float:
    """Return RSS sum for process tree in megabytes."""
    import psutil

    total_bytes = 0
    for proc in _collect_process_tree(root_proc):
        try:
            total_bytes += proc.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total_bytes / (1024 * 1024)


def bench_realtime_latency(
    model_id: str,
    language: str,
    *,
    targets: dict[str, float],
) -> dict[str, Any]:
    """Realtime path latency (README §3, P0 DoD ④) via realtime_latency bench."""
    from scripts.bench.realtime_latency import bench_realtime

    result = bench_realtime(model_id, language)
    if result.get("status") == "skip":
        return {"status": "skip", "reason": str(result.get("reason", "unavailable"))}

    target_ms = targets.get("realtime_target_ms", 1000)
    total_ms = float(result.get("total_ms", 0))
    return {
        "status": "ok",
        "model": model_id,
        "vad_end_ms": result.get("vad_end_ms"),
        "stt_ms": result.get("stt_ms"),
        "total_ms": total_ms,
        "target_ms": target_ms,
        "pass": total_ms < target_ms,
    }


def bench_idle_cpu_packaged(
    exe_path: Path,
    *,
    targets: dict[str, float],
) -> dict[str, Any]:
    """Launch packaged STT-AIO.exe and sample tray-idle CPU (P5 NFR)."""
    try:
        import psutil
    except ImportError:
        return {
            "status": "skip",
            "reason": "psutil not installed (pip install psutil)",
        }

    if not exe_path.is_file():
        return {
            "status": "skip",
            "reason": f"packaged exe not found: {exe_path}",
        }

    startup_sec = targets.get("packaged_startup_sec", 3.0)
    sample_sec = targets.get("idle_cpu_sample_sec", 1.5)
    target = targets["idle_cpu_percent"]

    proc = subprocess.Popen(
        [str(exe_path)],
        cwd=str(exe_path.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "STT_AIO_NFR_BENCH": "1"},
    )
    try:
        time.sleep(startup_sec)
        try:
            ps_proc = psutil.Process(proc.pid)
        except psutil.NoSuchProcess:
            return {
                "status": "error",
                "reason": "packaged exe exited before idle sample",
                "exe": str(exe_path),
            }

        cpu_percent = _sample_process_tree_cpu(ps_proc, sample_sec)
        memory_mb = _sample_process_tree_memory_mb(ps_proc)
        memory_target = targets.get("idle_memory_mb_max", 500)
        return {
            "status": "ok",
            "exe": str(exe_path),
            "pid": proc.pid,
            "cpu_percent": round(cpu_percent, 3),
            "memory_mb": round(memory_mb, 1),
            "startup_sec": startup_sec,
            "sample_sec": sample_sec,
            "target_percent": target,
            "memory_target_mb": memory_target,
            "cpu_pass": cpu_percent < target,
            "memory_pass": memory_mb < memory_target,
            "pass": cpu_percent < target and memory_mb < memory_target,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": str(exc), "exe": str(exe_path)}
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)


def bench_idle_cpu(*, targets: dict[str, float]) -> dict[str, Any]:
    """Sample current process CPU after warm-up sleep (proxy for tray idle)."""
    try:
        import psutil
    except ImportError:
        return {
            "status": "skip",
            "reason": "psutil not installed (pip install psutil)",
        }

    sample_sec = targets.get("idle_cpu_sample_sec", 1.5)
    proc = psutil.Process(os.getpid())
    proc.cpu_percent(None)
    time.sleep(sample_sec)
    cpu_percent = proc.cpu_percent(None) / max(psutil.cpu_count(logical=True) or 1, 1)
    target = targets["idle_cpu_percent"]
    return {
        "status": "ok",
        "cpu_percent": round(cpu_percent, 3),
        "sample_sec": sample_sec,
        "target_percent": target,
        "pass": cpu_percent < target,
        "note": "bench process proxy; run against packaged STT-AIO.exe for production NFR",
    }


def run_all(
    *,
    model_id: str,
    language: str,
    exe_path: Path | None = None,
) -> dict[str, Any]:
    targets = load_targets()
    packaged = exe_path or find_packaged_exe()
    packaged_expected = packaged is not None
    report: dict[str, Any] = {
        "targets": targets,
        "packaged_exe_expected": packaged_expected,
        "cold_start": bench_cold_start(model_id, language, targets=targets),
        "app_import": bench_app_import(targets=targets),
        "realtime_latency": bench_realtime_latency(model_id, language, targets=targets),
        "idle_cpu": bench_idle_cpu(targets=targets),
    }
    if packaged_expected:
        report["idle_cpu_packaged"] = bench_idle_cpu_packaged(packaged, targets=targets)
    else:
        report["idle_cpu_packaged"] = {
            "status": "skip",
            "reason": "dist/STT-AIO/STT-AIO.exe not found; build with build/build.py",
        }
    return report


def summarize(report: dict[str, Any]) -> bool:
    ok = True
    sections = ("cold_start", "app_import", "realtime_latency", "idle_cpu", "idle_cpu_packaged")
    for key in sections:
        section = report.get(key, {})
        status = section.get("status")
        if status == "ok":
            if key == "cold_start":
                ok = ok and section.get("warmup_pass", False) and section.get("transcribe_pass", False)
            else:
                ok = ok and section.get("pass", False)
        elif status == "error":
            ok = False
        elif status == "skip":
            if key == "idle_cpu_packaged" and report.get("packaged_exe_expected"):
                ok = False
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="STT-AIO NFR benchmarks (P5)")
    parser.add_argument("--model", default="tiny")
    parser.add_argument("--language", default="ko")
    parser.add_argument("--all", action="store_true", help="Run all NFR benches")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    parser.add_argument(
        "--exe-path",
        type=Path,
        default=None,
        help="Packaged STT-AIO.exe for idle_cpu_packaged bench",
    )
    args = parser.parse_args(argv)

    if args.all:
        report = run_all(
            model_id=args.model,
            language=args.language,
            exe_path=args.exe_path,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if summarize(report) else 1

    targets = load_targets()
    result = bench_cold_start(args.model, args.language, targets=targets)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") != "ok":
        return 0
    passed = result.get("warmup_pass") and result.get("transcribe_pass")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
