"""Remote gateway server LAN binding tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from remote.gateway.server import RemoteGatewayServer


def test_access_info_includes_lan_url_when_bound_all() -> None:
    server = RemoteGatewayServer(MagicMock(), host="0.0.0.0", port=8765)
    server._resolved_port = 8765
    with patch("remote.gateway.server.get_lan_ipv4", return_value="192.168.0.10"):
        info = server._build_access_info("1234")
    assert info.base_url == "http://127.0.0.1:8765"
    assert info.lan_url == "http://192.168.0.10:8765"
    assert info.bind_host == "0.0.0.0"


def test_access_info_omits_lan_url_on_loopback_bind() -> None:
    server = RemoteGatewayServer(MagicMock(), host="127.0.0.1", port=8765)
    server._resolved_port = 8765
    info = server._build_access_info("5678")
    assert info.lan_url is None
