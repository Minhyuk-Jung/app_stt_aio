"""Cloudflare Tunnel live smoke (C15 §10, P4) — skips without cloudflared."""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    if not shutil.which("cloudflared"):
        print("status=skip")
        print("reason=cloudflared not on PATH")
        return 0

    sys.path.insert(0, str(ROOT))
    from app.config import Config
    from app.session import SessionManager
    from remote.gateway.server import RemoteGatewayServer
    from remote.gateway.tunnel import CloudflareTunnel

    config = Config.open(ROOT / "build" / ".tunnel_smoke.db", migrate_backup=False)
    try:
        from unittest.mock import MagicMock

        manager = SessionManager(config, MagicMock())
        server = RemoteGatewayServer(manager, port=18765)
        access = server.start()
        tunnel = CloudflareTunnel(access.base_url)
        try:
            info = tunnel.start(timeout_sec=45.0, max_attempts=2)
            print(f"status=ok")
            print(f"public_url={info.public_url}")
            try:
                import httpx

                response = httpx.get(f"{info.public_url}/health", timeout=15.0)
                print(f"health_status={response.status_code}")
                return 0 if response.status_code == 200 else 1
            except Exception as exc:  # noqa: BLE001
                print(f"status=error")
                print(f"reason=health check failed: {exc}")
                return 1
        finally:
            tunnel.stop()
            server.stop()
    finally:
        config.close()
        smoke_db = ROOT / "build" / ".tunnel_smoke.db"
        if smoke_db.is_file():
            smoke_db.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
