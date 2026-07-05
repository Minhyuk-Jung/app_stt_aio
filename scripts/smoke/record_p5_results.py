"""Record P5 stabilization results (pytest + NFR + P4 smoke)."""

from __future__ import annotations

import platform
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "devplans" / "phases" / "P5-stabilization-results.md"


def _run_pytest() -> tuple[int, str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--ignore=tests/ui"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    out = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode, out


def _run_script(rel: str, *, timeout: int = 300) -> str:
    completed = subprocess.run(
        [sys.executable, rel],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return (completed.stdout or completed.stderr or "").strip()


def main() -> int:
    today = date.today().isoformat()
    env = f"Python {platform.python_version()} / {platform.system()}"
    exit_code, pytest_out = _run_pytest()
    pytest_status = "pass" if exit_code == 0 else f"fail(exit={exit_code})"

    p4_out = _run_script("scripts/smoke/record_p4_results.py", timeout=120)
    nfr_out = _run_script("scripts/bench/record_nfr_results.py", timeout=300)

    body = f"""# P5 Stabilization Results

자동 기록: `{Path(__file__).name}` ({today})

| 항목 | 날짜 | 환경 | 결과 |
|------|------|------|------|
| 전체 pytest (UI 제외) | {today} | {env} | {pytest_status} |
| P4 gateway smoke | {today} | {env} | `record_p4_results.py` |
| NFR bench | {today} | {env} | `record_nfr_results.py` |

## pytest

```
{pytest_out}
```

## record_p4_results

```
{p4_out}
```

## record_nfr_results

```
{nfr_out}
```

관련 문서: `devplans/phases/P5-handoff.md`, `docs/release_checklist.md`
"""
    RESULTS.write_text(body, encoding="utf-8")
    print(f"wrote {RESULTS}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
