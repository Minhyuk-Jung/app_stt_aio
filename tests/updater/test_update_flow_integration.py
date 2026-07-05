"""C22 end-to-end flow tests without Qt (P6 #12/#13 logic + core)."""

from __future__ import annotations

import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest

from app.ui.update_check_logic import (
    resolve_update_dialog_buttons,
    should_notify_update,
    should_offer_browser_fallback_on_download_fail,
)
from core.updater.checker import UpdateInfo, check_for_updates
from core.updater.downloader import download_update
from core.updater.verify import ChecksumMismatchError


def _manifest_handler_factory(manifest: dict, installer_bytes: bytes, checksum: str):
  class Handler(BaseHTTPRequestHandler):
      def log_message(self, *_args) -> None:
          return

      def do_GET(self) -> None:
          if self.path.endswith("manifest.json"):
              body = json.dumps(manifest).encode("utf-8")
              self.send_response(200)
              self.send_header("Content-Type", "application/json")
              self.end_headers()
              self.wfile.write(body)
              return
          if self.path.endswith("setup.exe"):
              self.send_response(200)
              self.send_header("Content-Length", str(len(installer_bytes)))
              self.end_headers()
              self.wfile.write(installer_bytes)
              return
          self.send_response(404)
          self.end_headers()

  return Handler


def _serve(handler_cls, port: int = 0) -> tuple[HTTPServer, int]:
    server = HTTPServer(("127.0.0.1", port), handler_cls)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_port


def test_check_download_apply_logic_chain(tmp_path: Path) -> None:
    """확인 → 다이얼로그 버튼 → 다운로드·검증 흐름 (C22 §10 통합, Qt 제외)."""
    payload = b"fake installer payload for C22"
    checksum = hashlib.sha256(payload).hexdigest()
    manifest = {
        "version": "9.9.9",
        "download_url": "",  # filled after server start
        "checksum_sha256": checksum,
        "release_notes": "integration test",
        "mandatory": False,
    }

    Handler = _manifest_handler_factory(manifest, payload, checksum)
    server, port = _serve(Handler)
    try:
        base = f"http://127.0.0.1:{port}"
        manifest["download_url"] = f"{base}/setup.exe"
        manifest_url = f"{base}/manifest.json"

        with patch("core.updater.checker.__version__", "0.1.0"):
            info = check_for_updates(manifest_url)

        assert info is not None
        assert should_notify_update(info) is True
        buttons = resolve_update_dialog_buttons(info)
        assert buttons == {"direct_download": True, "browser": True, "dismiss": True}

        dest = tmp_path / "STT-AIO-Setup-9.9.9.exe"
        download_update(
            info.download_url,
            dest,
            expected_sha256=info.checksum_sha256,
        )
        assert dest.read_bytes() == payload

        with pytest.raises(ChecksumMismatchError):
            download_update(
                info.download_url,
                tmp_path / "bad.exe",
                expected_sha256="0" * 64,
            )

        assert should_offer_browser_fallback_on_download_fail(info) is True
    finally:
        server.shutdown()


def test_mandatory_update_hides_dismiss_and_keeps_download() -> None:
    info = UpdateInfo(
        current_version="0.1.0",
        latest_version="1.0.0",
        download_url="https://cdn.example/setup.exe",
        release_notes="required",
        checksum_sha256="a" * 64,
        mandatory=True,
    )
    buttons = resolve_update_dialog_buttons(info)
    assert buttons["dismiss"] is False
    assert buttons["direct_download"] is True
