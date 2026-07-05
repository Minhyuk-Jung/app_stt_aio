"""Record P0 spike script output into P0-spike-results.md."""

from __future__ import annotations

import platform
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "devplans" / "phases" / "P0-spike-results.md"


def _run(cmd: list[str]) -> str:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        out = (completed.stdout or "").strip()
        err = (completed.stderr or "").strip()
        if completed.returncode != 0 and err:
            return f"exit={completed.returncode}\n{out}\n{err}".strip()
        return out or f"exit={completed.returncode}"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def main() -> int:
    py = sys.executable
    today = date.today().isoformat()
    env = f"Python {platform.python_version()} / {platform.system()}"

    inject_dry = _run([py, "scripts/spike/inject_ko_smoke.py", "--dry-run"])
    inject_cb = ""
    inject_paste = ""
    inject_notepad = ""
    if platform.system() == "Windows":
        inject_cb = _run([py, "scripts/spike/inject_ko_smoke.py", "--verify-clipboard"])
        inject_paste = _run([py, "scripts/spike/inject_ko_smoke.py", "--verify-paste"])
        inject_notepad = _run([py, "scripts/spike/inject_ko_smoke.py", "--inject-auto"])
    vad = _run([py, "scripts/bench/vad_segment.py"])
    stt = _run([py, "scripts/bench/stt_latency.py", "--model", "tiny"])
    realtime = _run([py, "scripts/bench/realtime_latency.py", "--model", "tiny"])
    ollama = _run([py, "scripts/spike/ollama_smoke.py"])
    wer = _run([py, "-m", "pytest", "tests/regression/ko_wer", "-q", "-m", "not integration"])
    nfr = _run([py, "scripts/bench/nfr_bench.py", "--all", "--json"])
    tunnel = _run([py, "scripts/smoke/tunnel_check.py"])

    body = f"""# P0 Spike Results

자동 기록: `{Path(__file__).name}` ({today})

| 항목 | 날짜 | 환경 | 결과 |
|------|------|------|------|
| 한글 주입 UTF-16 roundtrip | {today} | {env} | see below |
| 한글 클립보드 roundtrip | {today} | {env} | see below |
| 한글 paste 경로 (mock) | {today} | {env} | see below |
| SendInput UNICODE 자동 | {today} | {env} | see below |
| VAD 세그먼트 종료 | {today} | 시뮬레이션 | see below |
| STT 지연 (배치) | {today} | faster-whisper optional | see below |
| 실시간 경로 지연 | {today} | VAD+STT 시뮬레이션 | see below |
| Ollama 연결 | {today} | localhost:11434 optional | see below |
| 한국어 WER 회귀 | {today} | pytest | see below |
| NFR 벤치 (P5) | {today} | nfr_bench --all | see below |
| Tunnel CLI | {today} | cloudflared optional | see below |

## inject_ko_smoke --dry-run
```
{inject_dry}
```

## inject_ko_smoke --verify-clipboard
```
{inject_cb or "skipped (non-Windows)"}
```

## inject_ko_smoke --verify-paste
```
{inject_paste or "skipped (non-Windows)"}
```

## inject_ko_smoke --inject-auto
```
{inject_notepad or "skipped (non-Windows)"}
```

## vad_segment
```
{vad}
```

## stt_latency
```
{stt}
```

## realtime_latency
```
{realtime}
```

## ollama_smoke
```
{ollama}
```

## ko_wer pytest
```
{wer}
```

## nfr_bench --all
```
{nfr}
```

## tunnel_check
```
{tunnel}
```
"""
    RESULTS.write_text(body, encoding="utf-8")
    print(f"wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
