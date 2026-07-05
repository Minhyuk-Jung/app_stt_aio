"""Cloudflare Tunnel CLI availability check (C15 §7, P4)."""

from __future__ import annotations

import shutil
import subprocess
import sys


def main() -> int:
    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        print("status=skip")
        print("reason=cloudflared not on PATH")
        return 0
    try:
        completed = subprocess.run(
            [cloudflared, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        version = (completed.stdout or completed.stderr or "").strip().splitlines()
        first = version[0] if version else "unknown"
        print(f"status=ok")
        print(f"cloudflared={cloudflared}")
        print(f"version={first}")
        return 0 if completed.returncode == 0 else 1
    except Exception as exc:  # noqa: BLE001
        print(f"status=error")
        print(f"reason={exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
