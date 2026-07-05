"""LAN network helper tests (C15 §7)."""

from __future__ import annotations

from unittest.mock import patch

from remote.gateway.network import get_lan_ipv4


def test_get_lan_ipv4_returns_ip() -> None:
    with patch("remote.gateway.network.socket.socket") as mock_socket:
        sock = mock_socket.return_value.__enter__.return_value
        sock.getsockname.return_value = ("192.168.1.42", 54321)
        assert get_lan_ipv4() == "192.168.1.42"


def test_get_lan_ipv4_skips_loopback() -> None:
    with patch("remote.gateway.network.socket.socket") as mock_socket:
        sock = mock_socket.return_value.__enter__.return_value
        sock.getsockname.return_value = ("127.0.0.1", 54321)
        assert get_lan_ipv4() is None


def test_get_lan_ipv4_handles_socket_error() -> None:
    with patch("remote.gateway.network.socket.socket", side_effect=OSError("offline")):
        assert get_lan_ipv4() is None
