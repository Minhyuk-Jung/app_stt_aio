"""Remote gateway server lifecycle (C15 §6.1)."""

from __future__ import annotations

import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING

from remote.gateway.app import create_app
from remote.gateway.network import get_lan_ipv4
from remote.gateway.pairing import PairingManager

if TYPE_CHECKING:
    from app.session.session_manager import SessionManager

logger = logging.getLogger(__name__)

READY_TIMEOUT_SEC = 5.0


@dataclass(frozen=True)
class AccessInfo:
    base_url: str
    pin: str
    pwa_path: str
    lan_url: str | None = None
    bind_host: str = "127.0.0.1"


class RemoteGatewayServer:
    """Embed FastAPI + uvicorn in a background thread."""

    def __init__(
        self,
        session_manager: SessionManager,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        pairing: PairingManager | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._host = host
        self._port = port
        self._pairing = pairing or PairingManager()
        self._thread: threading.Thread | None = None
        self._server = None
        self._resolved_port = 0

    @property
    def pairing(self) -> PairingManager:
        return self._pairing

    @property
    def bind_host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._resolved_port or self._port

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, *, wait_ready: bool = True) -> AccessInfo:
        if self.is_running:
            return self.get_access_info()
        pin = self._pairing.current_pin() or self._pairing.issue_pin()
        self._run_uvicorn()
        self._resolved_port = self._port if self._port > 0 else 8765
        if wait_ready:
            self._wait_until_ready()
        return self._build_access_info(pin)

    def rebind(self, host: str, *, wait_ready: bool = True) -> AccessInfo:
        """Restart uvicorn on a new bind host without revoking pairing (C15 §7)."""
        if not self.is_running:
            raise RuntimeError("gateway is not running")
        pin = self._pairing.current_pin() or self._pairing.issue_pin()
        self._shutdown_uvicorn()
        self._host = host
        self._run_uvicorn()
        if wait_ready:
            self._wait_until_ready()
        return self._build_access_info(pin)

    def _run_uvicorn(self) -> None:
        app = create_app(self._session_manager, pairing=self._pairing)
        import uvicorn

        # Single worker only — ChunkAssembler is in-process (C15 §6.3).
        config = uvicorn.Config(app, host=self._host, port=self._port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="remote-gateway", daemon=True)
        self._thread.start()

    def _shutdown_uvicorn(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        self._server = None

    def _wait_until_ready(self) -> None:
        port = self._resolved_port or self._port
        url = f"http://127.0.0.1:{port}/health"
        deadline = time.time() + READY_TIMEOUT_SEC
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.05)
        logger.warning("Gateway /health wait timed out after %.1fs", READY_TIMEOUT_SEC)

    def _build_access_info(self, pin: str) -> AccessInfo:
        port = self._resolved_port or self._port
        lan_url: str | None = None
        if self._host == "0.0.0.0":
            lan_ip = get_lan_ipv4()
            if lan_ip:
                lan_url = f"http://{lan_ip}:{port}"
        return AccessInfo(
            base_url=f"http://127.0.0.1:{port}",
            pin=pin,
            pwa_path="/pwa/",
            lan_url=lan_url,
            bind_host=self._host,
        )

    def stop(self, *, revoke: bool = True) -> None:
        self._shutdown_uvicorn()
        if revoke:
            self._pairing.revoke_all()
        self._resolved_port = 0

    def get_access_info(self) -> AccessInfo:
        pin = self._pairing.current_pin() or self._pairing.issue_pin()
        return self._build_access_info(pin)
