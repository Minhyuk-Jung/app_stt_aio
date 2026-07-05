"""Record P5 NFR benchmark output into P5-nfr-results.md (README §3)."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "devplans" / "phases" / "P5-nfr-results.md"


def _run_nfr() -> str:
    py = sys.executable
    completed = subprocess.run(
        [py, "scripts/bench/nfr_bench.py", "--all", "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    out = (completed.stdout or "").strip()
    if not out and completed.stderr:
        return completed.stderr.strip()
    if completed.returncode != 0:
        return f"exit={completed.returncode}\n{out}"
    return out


def main() -> int:
    today = date.today().isoformat()
    env = f"Python {platform.python_version()} / {platform.system()}"
    raw = _run_nfr()
    parse_raw = raw.split("\n", 1)[-1] if raw.startswith("exit=") else raw
    try:
        payload = json.loads(parse_raw)
        pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        pretty = raw
        payload = None

    body = f"""# P5 NFR Results

자동 기록: `{Path(__file__).name}` ({today})

| 항목 | 날짜 | 환경 | 비고 |
|------|------|------|------|
| 콜드 스타트 / 첫 transcribe | {today} | {env} | faster-whisper optional |
| 코어 import 지연 | {today} | {env} | Qt 미기동 |
| 유휴 CPU 샘플 | {today} | {env} | psutil optional |
| 실시간 지연 (1초 목표) | {today} | {env} | realtime_latency |
| 패키지 exe 유휴 CPU/메모리 | {today} | {env} | dist/STT-AIO/STT-AIO.exe |

## nfr_bench --all

```json
{pretty}
```

목표값: `scripts/bench/nfr_targets.json` (README §3)
"""
    RESULTS.write_text(body, encoding="utf-8")
    print(f"wrote {RESULTS}")

    if payload is None:
        return 1

    packaged = payload.get("idle_cpu_packaged") or {}
    exe = ROOT / "dist" / "STT-AIO" / "STT-AIO.exe"
    if exe.is_file():
        if packaged.get("pass") is not True:
            return 1
        return 0

    # No packaged exe: record only (dev proxy may exceed target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
