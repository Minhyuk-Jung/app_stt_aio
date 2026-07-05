# P0 Spike Results

자동 기록: `record_p0_results.py` (2026-07-04)

| 항목 | 날짜 | 환경 | 결과 |
|------|------|------|------|
| 한글 주입 UTF-16 roundtrip | 2026-07-04 | Python 3.10.9 / Windows | see below |
| 한글 클립보드 roundtrip | 2026-07-04 | Python 3.10.9 / Windows | see below |
| 한글 paste 경로 (mock) | 2026-07-04 | Python 3.10.9 / Windows | see below |
| SendInput UNICODE 자동 | 2026-07-04 | Python 3.10.9 / Windows | see below |
| VAD 세그먼트 종료 | 2026-07-04 | 시뮬레이션 | see below |
| STT 지연 (배치) | 2026-07-04 | faster-whisper optional | see below |
| 실시간 경로 지연 | 2026-07-04 | VAD+STT 시뮬레이션 | see below |
| Ollama 연결 | 2026-07-04 | localhost:11434 optional | see below |
| 한국어 WER 회귀 | 2026-07-04 | pytest | see below |
| Tunnel CLI | 2026-07-04 | cloudflared optional | see below |

## inject_ko_smoke --dry-run
```
encoding_roundtrip=ok samples=3
hint: use --inject-notepad for automated SendInput test
hint: use --inject for live Windows test with manual focus
hint: use --verify-clipboard or --verify-paste for automated tests
```

## inject_ko_smoke --verify-clipboard
```
encoding_roundtrip=ok samples=3
clipboard_roundtrip=ok samples=3
```

## inject_ko_smoke --verify-paste
```
encoding_roundtrip=ok samples=3
paste_path=ok samples=3
```

## inject_ko_smoke --inject-auto
```
encoding_roundtrip=ok samples=3
inject_auto=ok samples=3 method=unicode
```

## vad_segment
```
vad_segment_end_ms=510.0
target_ms=530
pass=True
bench_overhead_ms=1.22
```

## stt_latency
```
status=ok
model=tiny
load_ms=817.9
transcribe_ms=9893.4
text_len=223
pass=False
target_ms=2000
```

## realtime_latency
```
status=ok
model=tiny
vad_end_ms=510
stt_ms=245.1
load_ms=719.4
total_ms=755.1
text_len=0
pass=True
target_ms=1000
```

## ollama_smoke
```
status=ok
message=connected
models=12
  - gemma4:26b
  - huihui_ai/qwen3.6-abliterated:27b
  - huihui_ai/gpt-oss-abliterated:latest
  - qwen3-embedding:0.6b
  - nomic-embed-text-v2-moe:latest
```

## ko_wer pytest
```
....                                                                     [100%]
4 passed, 1 deselected in 0.93s
```

## tunnel_check
```
status=skip
reason=cloudflared not on PATH
```
