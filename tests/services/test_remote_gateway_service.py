"""RemoteGatewayService unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.remote_gateway_service import RemoteGatewayService
from remote.gateway.server import AccessInfo


def test_start_stop_lifecycle() -> None:
    sessions = MagicMock()
    service = RemoteGatewayService(sessions)
    access = AccessInfo(base_url="http://127.0.0.1:8765", pin="1234", pwa_path="/pwa/")
    mock_server = MagicMock()
    mock_server.is_running = True
    mock_server.start.return_value = access

    with patch(
        "app.services.remote_gateway_service.RemoteGatewayServer",
        return_value=mock_server,
    ) as server_cls:
        info = service.start(port=8765, use_tunnel=False, lan_fallback=True)

    server_cls.assert_called_once()
    assert server_cls.call_args.kwargs["host"] == "127.0.0.1"
    assert info.pin == "1234"
    assert info.bind_host == "127.0.0.1"
    assert info.mobile_recording_available is False
    assert service.is_running
    service.stop()
    mock_server.stop.assert_called_once_with(revoke=True)


def test_start_rebinds_lan_when_tunnel_fails() -> None:
    sessions = MagicMock()
    service = RemoteGatewayService(sessions)
    loopback = AccessInfo(
        base_url="http://127.0.0.1:8765",
        pin="5678",
        pwa_path="/pwa/",
        bind_host="127.0.0.1",
    )
    lan = AccessInfo(
        base_url="http://127.0.0.1:8765",
        pin="5678",
        pwa_path="/pwa/",
        lan_url="http://192.168.1.5:8765",
        bind_host="0.0.0.0",
    )
    mock_server = MagicMock()
    mock_server.is_running = True
    mock_server.start.return_value = loopback
    mock_server.rebind.return_value = lan
    mock_tunnel = MagicMock()
    mock_tunnel.start.side_effect = RuntimeError("tunnel down")

    with patch(
        "app.services.remote_gateway_service.RemoteGatewayServer",
        return_value=mock_server,
    ) as server_cls:
        with patch(
            "app.services.remote_gateway_service.CloudflareTunnel",
            return_value=mock_tunnel,
        ):
            with patch(
                "app.services.remote_gateway_service.tunnel_available",
                return_value=True,
            ):
                info = service.start(port=8765, use_tunnel=True, lan_fallback=True)

    assert server_cls.call_args.kwargs["host"] == "127.0.0.1"
    mock_server.rebind.assert_called_once_with("0.0.0.0")
    assert info.public_url is None
    assert info.lan_url == "http://192.168.1.5:8765"
    assert info.tunnel_failed is True
    assert info.tunnel_error == "tunnel down"
    assert info.mobile_recording_available is False


def test_start_stays_loopback_when_tunnel_fails_without_lan_fallback() -> None:
    sessions = MagicMock()
    service = RemoteGatewayService(sessions)
    access = AccessInfo(base_url="http://127.0.0.1:8765", pin="9999", pwa_path="/pwa/")
    mock_server = MagicMock()
    mock_server.is_running = True
    mock_server.start.return_value = access
    mock_tunnel = MagicMock()
    mock_tunnel.start.side_effect = RuntimeError("tunnel down")

    with patch(
        "app.services.remote_gateway_service.RemoteGatewayServer",
        return_value=mock_server,
    ):
        with patch(
            "app.services.remote_gateway_service.CloudflareTunnel",
            return_value=mock_tunnel,
        ):
            with patch(
                "app.services.remote_gateway_service.tunnel_available",
                return_value=True,
            ):
                info = service.start(port=8765, use_tunnel=True, lan_fallback=False)

    mock_server.rebind.assert_not_called()
    assert info.tunnel_failed is True
    assert info.lan_url is None


def test_diagnostics_snapshot() -> None:
    sessions = MagicMock()
    service = RemoteGatewayService(sessions)
    access = AccessInfo(base_url="http://127.0.0.1:8765", pin="9999", pwa_path="/pwa/")
    mock_server = MagicMock()
    mock_server.is_running = True
    mock_server.start.return_value = access
    mock_server.bind_host = "127.0.0.1"

    with patch(
        "app.services.remote_gateway_service.RemoteGatewayServer",
        return_value=mock_server,
    ):
        service.start(lan_fallback=False)

    snap = service.diagnostics_snapshot()
    assert snap["running"] is True
    assert snap["bind_host"] == "127.0.0.1"
    assert snap["port"] == 8765
    assert snap["mobile_recording_available"] is False


def test_tunnel_disconnect_clears_public_url() -> None:
    """C15 §10 — tunnel process end updates access + diagnostics (P5)."""
    sessions = MagicMock()
    service = RemoteGatewayService(sessions)
    loopback = AccessInfo(base_url="http://127.0.0.1:8765", pin="1111", pwa_path="/pwa/")
    mock_server = MagicMock()
    mock_server.is_running = True
    mock_server.start.return_value = loopback
    mock_server.get_access_info.return_value = loopback
    mock_server.bind_host = "127.0.0.1"
    mock_tunnel = MagicMock()
    tunnel_info = MagicMock()
    tunnel_info.public_url = "https://tunnel.example.com"
    mock_tunnel.start.return_value = tunnel_info
    mock_tunnel.is_running = True

    with patch(
        "app.services.remote_gateway_service.RemoteGatewayServer",
        return_value=mock_server,
    ):
        with patch(
            "app.services.remote_gateway_service.CloudflareTunnel",
            return_value=mock_tunnel,
        ):
            with patch(
                "app.services.remote_gateway_service.tunnel_available",
                return_value=True,
            ):
                info = service.start(port=8765, use_tunnel=True, lan_fallback=False)

    assert info.public_url == "https://tunnel.example.com"
    assert info.mobile_recording_available is True

    mock_tunnel.is_running = False
    refreshed = service.access_info
    assert refreshed is not None
    assert refreshed.public_url is None
    assert refreshed.tunnel_failed is True
    assert refreshed.tunnel_error == "tunnel disconnected"
    assert refreshed.mobile_recording_available is False

    snap = service.diagnostics_snapshot()
    assert snap["tunnel_connected"] is False
    assert snap["tunnel_failed"] is True
    assert snap["mobile_recording_available"] is False
