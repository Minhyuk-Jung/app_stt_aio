"""Tests for C22 Updater — verify, download, checker (P5)."""

from __future__ import annotations

import hashlib
import json
import socket
import struct
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

from core.updater.checker import UpdateInfo, check_for_updates
from core.updater.downloader import DownloadError, apply_update, download_update
from core.updater.verify import (
    ChecksumMismatchError,
    compute_sha256,
    verify_checksum,
)


# ---------------------------------------------------------------------------
# verify.py — checksum tests
# ---------------------------------------------------------------------------


def test_compute_sha256_matches_hashlib(tmp_path: Path) -> None:
    """compute_sha256 produces the same digest as hashlib directly."""
    data = b"STT-AIO test payload " * 1000
    f = tmp_path / "payload.bin"
    f.write_bytes(data)

    expected = hashlib.sha256(data).hexdigest()
    assert compute_sha256(f) == expected


def test_verify_checksum_passes_for_correct_digest(tmp_path: Path) -> None:
    data = b"correct payload"
    f = tmp_path / "installer.exe"
    f.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()

    verify_checksum(f, digest)  # must not raise


def test_verify_checksum_raises_for_wrong_digest(tmp_path: Path) -> None:
    data = b"correct payload"
    f = tmp_path / "installer.exe"
    f.write_bytes(data)

    with pytest.raises(ChecksumMismatchError, match="mismatch"):
        verify_checksum(f, "a" * 64)  # wrong digest


def test_verify_checksum_raises_if_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        verify_checksum(tmp_path / "nonexistent.exe", "a" * 64)


def test_verify_checksum_strips_and_lowercases_expected(tmp_path: Path) -> None:
    """Uppercase/whitespace-padded expected digest is accepted."""
    data = b"data"
    f = tmp_path / "a.exe"
    f.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()

    verify_checksum(f, "  " + digest.upper() + "  ")  # must not raise


# ---------------------------------------------------------------------------
# checker.py — manifest parsing
# ---------------------------------------------------------------------------


def test_check_for_updates_returns_none_when_url_empty() -> None:
    assert check_for_updates(None) is None
    assert check_for_updates("") is None
    assert check_for_updates("   ") is None


def test_check_for_updates_returns_none_on_network_error() -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("no network")):
        assert check_for_updates("https://example.com/manifest.json") is None


def test_check_for_updates_returns_none_when_same_version() -> None:
    from core.version import __version__

    payload = json.dumps({"version": __version__}).encode()
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = check_for_updates("https://example.com/manifest.json")

    assert result is None


def test_check_for_updates_parses_full_manifest() -> None:
    payload = json.dumps({
        "version": "99.0.0",
        "download_url": "https://example.com/Setup.exe",
        "release_notes": "Bug fixes",
        "checksum_sha256": "abc" * 21 + "a",  # 64 hex chars
        "mandatory": True,
    }).encode()
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.headers = {}

    with patch("urllib.request.urlopen", return_value=mock_response):
        info = check_for_updates("https://example.com/manifest.json")

    assert info is not None
    assert info.latest_version == "99.0.0"
    assert info.download_url == "https://example.com/Setup.exe"
    assert info.release_notes == "Bug fixes"
    assert info.checksum_sha256 == "abc" * 21 + "a"
    assert info.mandatory is True


def test_update_info_defaults_are_safe() -> None:
    """checksum_sha256 and mandatory have safe defaults."""
    info = UpdateInfo(
        current_version="0.1.0",
        latest_version="0.2.0",
        download_url=None,
        release_notes="",
    )
    assert info.checksum_sha256 is None
    assert info.mandatory is False


# ---------------------------------------------------------------------------
# downloader.py — download_update (mock HTTP)
# ---------------------------------------------------------------------------


class _SimpleFileServer(BaseHTTPRequestHandler):
    """Minimal HTTP server that serves a fixed payload."""

    payload: bytes = b""

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, *args):  # silence
        pass


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_download_update_saves_file(tmp_path: Path) -> None:
    """download_update writes the payload to dest_path."""
    payload = b"fake installer binary"
    _SimpleFileServer.payload = payload

    port = _find_free_port()
    server = HTTPServer(("127.0.0.1", port), _SimpleFileServer)
    t = Thread(target=server.handle_request, daemon=True)
    t.start()

    dest = tmp_path / "Setup.exe"
    result = download_update(f"http://127.0.0.1:{port}/Setup.exe", dest)

    t.join(timeout=5)
    server.server_close()

    assert result == dest
    assert dest.read_bytes() == payload


def test_download_update_with_valid_checksum(tmp_path: Path) -> None:
    """download_update verifies checksum and does not raise on match."""
    payload = b"valid installer"
    sha256 = hashlib.sha256(payload).hexdigest()
    _SimpleFileServer.payload = payload

    port = _find_free_port()
    server = HTTPServer(("127.0.0.1", port), _SimpleFileServer)
    t = Thread(target=server.handle_request, daemon=True)
    t.start()

    dest = tmp_path / "Setup.exe"
    download_update(
        f"http://127.0.0.1:{port}/Setup.exe",
        dest,
        expected_sha256=sha256,
    )

    t.join(timeout=5)
    server.server_close()
    assert dest.exists()


def test_download_update_raises_on_bad_checksum(tmp_path: Path) -> None:
    """download_update raises ChecksumMismatchError and leaves no partial file."""
    payload = b"tampered installer"
    _SimpleFileServer.payload = payload

    port = _find_free_port()
    server = HTTPServer(("127.0.0.1", port), _SimpleFileServer)
    t = Thread(target=server.handle_request, daemon=True)
    t.start()

    dest = tmp_path / "Setup.exe"
    with pytest.raises(ChecksumMismatchError):
        download_update(
            f"http://127.0.0.1:{port}/Setup.exe",
            dest,
            expected_sha256="a" * 64,  # wrong digest
        )

    t.join(timeout=5)
    server.server_close()
    # partial temp file cleaned up; dest must not exist
    assert not dest.exists()


def test_download_update_progress_callback(tmp_path: Path) -> None:
    """on_progress is called with increasing byte counts."""
    payload = b"x" * 1000
    _SimpleFileServer.payload = payload

    port = _find_free_port()
    server = HTTPServer(("127.0.0.1", port), _SimpleFileServer)
    t = Thread(target=server.handle_request, daemon=True)
    t.start()

    calls: list[tuple[int, int]] = []
    dest = tmp_path / "Setup.exe"
    download_update(
        f"http://127.0.0.1:{port}/Setup.exe",
        dest,
        on_progress=lambda done, total: calls.append((done, total)),
    )

    t.join(timeout=5)
    server.server_close()
    assert len(calls) >= 1
    assert calls[-1][0] == 1000  # all bytes reported


def test_download_update_raises_on_network_error(tmp_path: Path) -> None:
    """DownloadError is raised when the URL is unreachable."""
    dest = tmp_path / "Setup.exe"
    with pytest.raises(DownloadError):
        download_update("http://127.0.0.1:1/Setup.exe", dest)


# ---------------------------------------------------------------------------
# apply_update — Windows-only, just verify guard logic
# ---------------------------------------------------------------------------


def test_apply_update_raises_if_not_exe(tmp_path: Path) -> None:
    f = tmp_path / "manifest.json"
    f.write_text("{}")
    with pytest.raises(ValueError, match=r"\.exe"):
        apply_update(f)


def test_apply_update_raises_if_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        apply_update(tmp_path / "nonexistent.exe")


def test_default_installer_path_uses_updates_dir(tmp_path: Path, monkeypatch) -> None:
    from core.paths import AppPaths
    from core.updater.downloader import default_installer_path

    monkeypatch.setattr(
        "core.paths.get_app_paths",
        lambda: AppPaths(
            root=tmp_path,
            db=tmp_path / "app.db",
            models=tmp_path / "models",
            audio=tmp_path / "audio",
            logs=tmp_path / "logs",
        ),
    )
    path = default_installer_path("1.2.3")
    assert path.parent.name == "updates"
    assert path.name == "STT-AIO-Setup-1.2.3.exe"


def test_update_info_supports_direct_download() -> None:
    with_checksum = UpdateInfo(
        current_version="0.1.0",
        latest_version="0.2.0",
        download_url="https://example.com/Setup.exe",
        release_notes="",
        checksum_sha256="a" * 64,
    )
    without_checksum = UpdateInfo(
        current_version="0.1.0",
        latest_version="0.2.0",
        download_url="https://example.com/Setup.exe",
        release_notes="",
    )
    assert with_checksum.supports_direct_download is True
    assert without_checksum.supports_direct_download is False
