"""C22 updater checker tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from core.updater.checker import check_for_updates


def test_check_for_updates_empty_url() -> None:
    assert check_for_updates("") is None
    assert check_for_updates(None) is None


def test_check_for_updates_new_version() -> None:
    payload = json.dumps(
        {
            "version": "9.9.9",
            "download_url": "https://example.com/app.exe",
            "release_notes": "Test release",
        }
    ).encode()
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__.return_value = response
    with patch("urllib.request.urlopen", return_value=response):
        info = check_for_updates("https://example.com/manifest.json")
    assert info is not None
    assert info.latest_version == "9.9.9"
    assert info.download_url == "https://example.com/app.exe"
