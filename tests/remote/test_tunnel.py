"""Cloudflare Tunnel helper tests (C15 §7, P4)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from remote.gateway.tunnel import CloudflareTunnel, TunnelInfo, tunnel_available


def test_tunnel_available_false_when_missing(monkeypatch) -> None:
    monkeypatch.setattr("remote.gateway.tunnel.shutil.which", lambda _name: None)
    assert tunnel_available() is False


def test_tunnel_start_parses_public_url(monkeypatch) -> None:
    lines = [
        "INF Thank you for trying Cloudflare Tunnel\n",
        "INF |  https://abc.trycloudflare.com  |\n",
        "",
    ]
    stdout = MagicMock()
    stdout.readline.side_effect = lines

    def fake_popen(cmd, **kwargs):  # noqa: ANN001
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdout = stdout
        return proc

    monkeypatch.setattr("remote.gateway.tunnel.shutil.which", lambda _name: "/bin/cloudflared")
    monkeypatch.setattr("remote.gateway.tunnel.subprocess.Popen", fake_popen)

    tunnel = CloudflareTunnel("http://127.0.0.1:8765")
    info = tunnel.start(timeout_sec=2.0)
    assert info.public_url == "https://abc.trycloudflare.com"
    assert info.local_url == "http://127.0.0.1:8765"
    tunnel.stop()


def test_tunnel_start_raises_when_cloudflared_missing(monkeypatch) -> None:
    monkeypatch.setattr("remote.gateway.tunnel.shutil.which", lambda _name: None)
    tunnel = CloudflareTunnel("http://127.0.0.1:8765")
    with pytest.raises(RuntimeError, match="cloudflared"):
        tunnel.start(max_attempts=1)


def test_tunnel_start_retries_then_succeeds(monkeypatch) -> None:
    calls = {"count": 0}

    class FakeTunnel(CloudflareTunnel):
        def _start_once(self, *, timeout_sec: float) -> TunnelInfo:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("temporary")
            return TunnelInfo(
                public_url="https://retry.trycloudflare.com",
                local_url=self._local_url,
            )

    tunnel = FakeTunnel("http://127.0.0.1:8765")
    info = tunnel.start(max_attempts=2, timeout_sec=1.0)
    assert info.public_url == "https://retry.trycloudflare.com"
    assert calls["count"] == 2
