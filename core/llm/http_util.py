"""Minimal HTTP helpers with retry (stdlib only)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from core.llm.errors import AuthenticationError, CompletionError, ContextExceededError, NetworkError


def _build_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> urllib.request.Request:
    data = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    return urllib.request.Request(url, data=data, headers=req_headers, method=method)


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 120.0,
    retries: int = 2,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = _build_request(
                url,
                method=method,
                payload=payload,
                headers=headers,
                timeout=timeout,
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body.strip() else {}
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            lowered = message.lower()
            if exc.code in (401, 403):
                raise AuthenticationError(message or f"HTTP {exc.code}") from exc
            if exc.code == 400 and (
                "context" in lowered
                or "token" in lowered and "limit" in lowered
            ):
                raise ContextExceededError(message or "context length exceeded") from exc
            if exc.code == 404:
                raise CompletionError(message or f"HTTP {exc.code}") from exc
            if 500 <= exc.code < 600 and attempt < retries:
                time.sleep(0.2 * (2**attempt))
                last_error = CompletionError(message or f"HTTP {exc.code}")
                continue
            raise CompletionError(message or f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            last_error = NetworkError(str(exc.reason))
            if attempt < retries:
                time.sleep(0.2 * (2**attempt))
                continue
            raise last_error from exc
        except TimeoutError as exc:
            last_error = NetworkError("request timed out")
            if attempt < retries:
                time.sleep(0.2 * (2**attempt))
                continue
            raise last_error from exc
    if last_error is not None:
        raise last_error
    raise NetworkError("request failed")
