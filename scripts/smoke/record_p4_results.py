"""Record P4 remote gateway validation into P4-results.md (C15 §10, README §8 P4)."""

from __future__ import annotations

import platform
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "devplans" / "phases" / "P4-results.md"


def _run_pytest_remote() -> tuple[int, str]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/remote",
            "tests/services/test_remote_gateway_service.py",
            "-q",
            "--tb=no",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    out = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, out.strip()


def _run_tunnel_check() -> str:
    completed = subprocess.run(
        [sys.executable, "scripts/smoke/tunnel_check.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return (completed.stdout or completed.stderr or "").strip()


def _run_tunnel_live() -> str:
    completed = subprocess.run(
        [sys.executable, "scripts/smoke/tunnel_live_smoke.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return (completed.stdout or completed.stderr or "").strip()


def main() -> int:
    today = date.today().isoformat()
    env = f"Python {platform.python_version()} / {platform.system()}"
    exit_code, pytest_out = _run_pytest_remote()
    tunnel_out = _run_tunnel_check()
    tunnel_live_out = _run_tunnel_live()
    tunnel_status = "ok" if "status=ok" in tunnel_out else "skip"
    tunnel_live_status = "ok" if "status=ok" in tunnel_live_out else "skip"

    body = f"""# P4 Remote Gateway Results

자동 기록: `{Path(__file__).name}` ({today})

| 항목 | 날짜 | 환경 | 결과 |
|------|------|------|------|
| Gateway E2E (pair → upload → session) | {today} | {env} | pytest exit={exit_code} |
| 업로드 보안 (401/413/400) | {today} | {env} | `tests/remote/test_gateway_security.py` |
| Artifact DB 연동 | {today} | {env} | `tests/remote/test_gateway_session.py` |
| Cloudflare Tunnel CLI | {today} | {env} | {tunnel_status} |
| Cloudflare Tunnel live `/health` | {today} | {env} | {tunnel_live_status} |
| 모바일 브라우저 실기기 E2E | — | — | **수동** (`docs/p4_mobile_e2e.md`) |

## pytest (tests/remote + gateway service)

```
{pytest_out}
```

## tunnel_check

```
{tunnel_out}
```

## tunnel_live_smoke

```
{tunnel_live_out}
```

계획서: `devplans/initial/C15-remote-gateway.md` §10
"""
    RESULTS.write_text(body, encoding="utf-8")
    print(f"wrote {RESULTS}")
    return 0 if exit_code == 0 else exit_code


if __name__ == "__main__":
    raise SystemExit(main())
