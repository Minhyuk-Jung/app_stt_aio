"""App-layer remote gateway lifecycle (C15)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from remote.gateway.server import AccessInfo, RemoteGatewayServer
from remote.gateway.tunnel import CloudflareTunnel, TunnelInfo, tunnel_available

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RemoteAccessInfo:
    local_url: str
    pin: str
    pwa_url: str
    public_url: str | None = None
    lan_url: str | None = None
    tunnel_failed: bool = False
    tunnel_error: str | None = None
    bind_host: str = "127.0.0.1"
    port: int = 8765
    mobile_recording_available: bool = False

    @classmethod
    def from_access(
        cls,
        info: AccessInfo,
        *,
        public_url: str | None = None,
        tunnel_failed: bool = False,
        tunnel_error: str | None = None,
        port: int = 8765,
    ) -> RemoteAccessInfo:
        base = info.base_url.rstrip("/")
        if public_url:
            pwa_base = public_url.rstrip("/")
        else:
            pwa_base = base
        return cls(
            local_url=base,
            pin=info.pin,
            pwa_url=f"{pwa_base}{info.pwa_path}",
            public_url=public_url,
            lan_url=info.lan_url,
            tunnel_failed=tunnel_failed,
            tunnel_error=tunnel_error,
            bind_host=info.bind_host,
            port=port,
            mobile_recording_available=public_url is not None,
        )


class RemoteGatewayService:
    """Start/stop gateway and optional Cloudflare tunnel for UI layer."""

    def __init__(self, session_manager) -> None:
        self._session_manager = session_manager
        self._server: RemoteGatewayServer | None = None
        self._tunnel: CloudflareTunnel | None = None
        self._access: RemoteAccessInfo | None = None
        self._port = 8765
        self._lan_fallback_enabled = True

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._server.is_running

    @property
    def access_info(self) -> RemoteAccessInfo | None:
        self._sync_tunnel_status()
        return self._access

    def can_use_tunnel(self) -> bool:
        return tunnel_available()

    def tunnel_is_connected(self) -> bool:
        return self._tunnel is not None and self._tunnel.is_running

    def start(
        self,
        *,
        port: int = 8765,
        use_tunnel: bool = False,
        lan_fallback: bool = True,
    ) -> RemoteAccessInfo:
        if self.is_running:
            return self._access or self._refresh_access()
        self._port = port
        self._lan_fallback_enabled = lan_fallback
        self._server = RemoteGatewayServer(
            self._session_manager,
            host="127.0.0.1",
            port=port,
        )
        info = self._server.start()
        public_url: str | None = None
        tunnel_failed = False
        tunnel_error: str | None = None

        if use_tunnel:
            self._tunnel = CloudflareTunnel(info.base_url)
            try:
                tunnel_info: TunnelInfo = self._tunnel.start(max_attempts=2)
                public_url = tunnel_info.public_url
            except Exception as exc:  # noqa: BLE001
                tunnel_failed = True
                tunnel_error = str(exc)
                logger.warning("Tunnel start failed: %s", exc)
                self._tunnel = None
                if lan_fallback:
                    info = self._server.rebind("0.0.0.0")

        self._access = RemoteAccessInfo.from_access(
            info,
            public_url=public_url,
            tunnel_failed=tunnel_failed,
            tunnel_error=tunnel_error,
            port=port,
        )
        return self._access

    def stop(self) -> None:
        if self._tunnel is not None:
            self._tunnel.stop()
            self._tunnel = None
        if self._server is not None:
            self._server.stop(revoke=True)
            self._server = None
        self._access = None

    def _sync_tunnel_status(self) -> None:
        if self._tunnel is None or self._access is None or self._server is None:
            return
        if self._tunnel.is_running:
            return
        logger.warning("Cloudflare tunnel process ended unexpectedly")
        self._tunnel = None
        info = self._server.get_access_info()
        self._access = RemoteAccessInfo.from_access(
            info,
            public_url=None,
            tunnel_failed=True,
            tunnel_error="tunnel disconnected",
            port=self._port,
        )

    def _refresh_access(self) -> RemoteAccessInfo:
        assert self._server is not None
        self._sync_tunnel_status()
        info = self._server.get_access_info()
        public = self._access.public_url if self._access else None
        tunnel_failed = self._access.tunnel_failed if self._access else False
        tunnel_error = self._access.tunnel_error if self._access else None
        if public and not self.tunnel_is_connected():
            public = None
            tunnel_failed = True
            tunnel_error = tunnel_error or "tunnel disconnected"
        self._access = RemoteAccessInfo.from_access(
            info,
            public_url=public,
            tunnel_failed=tunnel_failed,
            tunnel_error=tunnel_error,
            port=self._port,
        )
        return self._access

    def diagnostics_snapshot(self) -> dict[str, object]:
        """C20: export-friendly gateway status."""
        self._sync_tunnel_status()
        info = self._access
        server = self._server
        return {
            "running": self.is_running,
            "tunnel_available": self.can_use_tunnel(),
            "tunnel_connected": self.tunnel_is_connected(),
            "bind_host": server.bind_host if server else None,
            "port": self._port,
            "lan_fallback_enabled": self._lan_fallback_enabled,
            "local_url": info.local_url if info else None,
            "lan_url": info.lan_url if info else None,
            "public_url": info.public_url if info else None,
            "tunnel_failed": info.tunnel_failed if info else False,
            "tunnel_error": info.tunnel_error if info else None,
            "mobile_recording_available": info.mobile_recording_available if info else False,
            "pin_active": bool(info and info.pin),
        }
