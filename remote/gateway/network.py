"""LAN network helpers for remote gateway (C15 §7)."""

from __future__ import annotations

import socket


def get_lan_ipv4() -> str | None:
    """Best-effort primary LAN IPv4 (non-loopback)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
    except OSError:
        return None
    if not ip or ip.startswith("127."):
        return None
    return ip
