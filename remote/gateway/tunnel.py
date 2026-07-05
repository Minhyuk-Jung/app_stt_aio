"""Cloudflare Tunnel helper (C15 §6.1) — optional external HTTPS."""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TunnelInfo:
    public_url: str
    local_url: str


class CloudflareTunnel:
    """Run `cloudflared tunnel --url` and parse the public HTTPS URL."""

    def __init__(self, local_url: str) -> None:
        self._local_url = local_url
        self._process: subprocess.Popen[str] | None = None
        self._public_url: str | None = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(
        self,
        *,
        timeout_sec: float = 30.0,
        max_attempts: int = 2,
    ) -> TunnelInfo:
        if self.is_running:
            return TunnelInfo(
                public_url=self._public_url or self._local_url,
                local_url=self._local_url,
            )
        attempts = max(1, max_attempts)
        last_error: RuntimeError | None = None
        for attempt in range(attempts):
            try:
                return self._start_once(timeout_sec=timeout_sec)
            except RuntimeError as exc:
                last_error = exc
                logger.warning(
                    "Tunnel start attempt %s/%s failed: %s",
                    attempt + 1,
                    attempts,
                    exc,
                )
                self.stop()
        assert last_error is not None
        raise last_error

    def _start_once(self, *, timeout_sec: float) -> TunnelInfo:
        cloudflared = shutil.which("cloudflared")
        if not cloudflared:
            raise RuntimeError(
                "cloudflared가 PATH에 없습니다. "
                "로컬 네트워크만 사용하거나 Cloudflare Tunnel CLI를 설치하세요."
            )
        self._process = subprocess.Popen(
            [cloudflared, "tunnel", "--url", self._local_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self._process.poll() is not None:
                break
            line = ""
            if self._process.stdout is not None:
                line = self._process.stdout.readline()
            if "https://" in line:
                for token in line.split():
                    if token.startswith("https://"):
                        self._public_url = token.strip()
                        return TunnelInfo(
                            public_url=self._public_url,
                            local_url=self._local_url,
                        )
            time.sleep(0.1)
        self.stop()
        raise RuntimeError("터널 URL을 가져오지 못했습니다 (시간 초과)")

    def stop(self) -> None:
        proc = self._process
        self._process = None
        self._public_url = None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=5.0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("tunnel stop: %s", exc)
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass


def tunnel_available() -> bool:
    return shutil.which("cloudflared") is not None
