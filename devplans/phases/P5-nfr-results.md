# P5 NFR Results

자동 기록: `record_nfr_results.py` (2026-07-05)

| 항목 | 날짜 | 환경 | 비고 |
|------|------|------|------|
| 콜드 스타트 / 첫 transcribe | 2026-07-05 | Python 3.10.9 / Windows | faster-whisper optional |
| 코어 import 지연 | 2026-07-05 | Python 3.10.9 / Windows | Qt 미기동 |
| 유휴 CPU 샘플 | 2026-07-05 | Python 3.10.9 / Windows | psutil optional |
| 실시간 지연 (1초 목표) | 2026-07-05 | Python 3.10.9 / Windows | realtime_latency |
| 패키지 exe 유휴 CPU/메모리 | 2026-07-05 | Python 3.10.9 / Windows | dist/STT-AIO/STT-AIO.exe |

## nfr_bench --all

```json
{
  "targets": {
    "cold_start_warmup_ms": 3000.0,
    "first_transcribe_ms": 2000.0,
    "app_import_ms": 3000.0,
    "realtime_target_ms": 1000.0,
    "idle_cpu_percent": 1.0,
    "idle_cpu_sample_sec": 1.5,
    "packaged_startup_sec": 3.0,
    "idle_memory_mb_max": 500.0
  },
  "packaged_exe_expected": true,
  "cold_start": {
    "status": "ok",
    "model": "tiny",
    "language": "ko",
    "warmup_ms": 2005.2,
    "first_transcribe_ms": 810.0,
    "text_len": 106,
    "warmup_pass": true,
    "transcribe_pass": true,
    "warmup_target_ms": 3000.0,
    "transcribe_target_ms": 2000.0
  },
  "app_import": {
    "status": "ok",
    "import_ms": 5.3,
    "target_ms": 3000.0,
    "pass": true
  },
  "realtime_latency": {
    "status": "ok",
    "model": "tiny",
    "vad_end_ms": 510,
    "stt_ms": 308.1,
    "total_ms": 818.1,
    "target_ms": 1000.0,
    "pass": true
  },
  "idle_cpu": {
    "status": "ok",
    "cpu_percent": 1.031,
    "sample_sec": 1.5,
    "target_percent": 1.0,
    "pass": false,
    "note": "bench process proxy; run against packaged STT-AIO.exe for production NFR"
  },
  "idle_cpu_packaged": {
    "status": "ok",
    "exe": "C:\\Users\\MJ_Home\\workspaces\\app_stt_aio\\dist\\STT-AIO\\STT-AIO.exe",
    "pid": 60232,
    "cpu_percent": 0.0,
    "memory_mb": 337.5,
    "startup_sec": 3.0,
    "sample_sec": 1.5,
    "target_percent": 1.0,
    "memory_target_mb": 500.0,
    "cpu_pass": true,
    "memory_pass": true,
    "pass": true
  }
}
```

목표값: `scripts/bench/nfr_targets.json` (README §3)
