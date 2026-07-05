"""Tests for LLM HTTP helper."""

from __future__ import annotations

import io
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from core.llm.errors import AuthenticationError, ContextExceededError, NetworkError
from core.llm.http_util import request_json


def _response(body: bytes = b'{"ok": true}') -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def test_request_json_retries_on_server_error() -> None:
    calls = {"count": 0}

    def fake_urlopen(_req, timeout=0):
        calls["count"] += 1
        if calls["count"] < 3:
            raise urllib.error.HTTPError(
                url="http://x",
                code=503,
                msg="down",
                hdrs=None,
                fp=io.BytesIO(b"temporary"),
            )
        return _response()

    with patch("core.llm.http_util.urllib.request.urlopen", side_effect=fake_urlopen):
        data = request_json("http://x/api", retries=2)

    assert data == {"ok": True}
    assert calls["count"] == 3


def test_request_json_maps_context_exceeded() -> None:
    def fake_urlopen(_req, timeout=0):
        raise urllib.error.HTTPError(
            url="http://x",
            code=400,
            msg="bad",
            hdrs=None,
            fp=io.BytesIO(b"context length exceeded"),
        )

    with patch("core.llm.http_util.urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(ContextExceededError):
            request_json("http://x/api", retries=0)


def test_request_json_does_not_retry_auth_errors() -> None:
    def fake_urlopen(_req, timeout=0):
        raise urllib.error.HTTPError(
            url="http://x",
            code=401,
            msg="unauthorized",
            hdrs=None,
            fp=io.BytesIO(b"nope"),
        )

    with patch("core.llm.http_util.urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(AuthenticationError):
            request_json("http://x/api", retries=2)


def test_request_json_retries_network_errors() -> None:
    calls = {"count": 0}

    def fake_urlopen(_req, timeout=0):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.URLError("connection reset")
        return _response()

    with patch("core.llm.http_util.urllib.request.urlopen", side_effect=fake_urlopen):
        data = request_json("http://x/api", retries=1)

    assert data == {"ok": True}
    assert calls["count"] == 2
