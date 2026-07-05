"""HTTP helpers for cloud STT (C2 §7, retries)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from core.stt.errors import AuthenticationError, NetworkError, TranscriptionError


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 60.0,
    retries: int = 2,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            data = None
            req_headers = {"Accept": "application/json"}
            if headers:
                req_headers.update(headers)
            if payload is not None:
                data = json.dumps(payload).encode("utf-8")
                req_headers.setdefault("Content-Type", "application/json")
            req = urllib.request.Request(
                url,
                data=data,
                headers=req_headers,
                method=method,
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body.strip() else {}
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            if exc.code in (401, 403):
                raise AuthenticationError(message or f"HTTP {exc.code}") from exc
            if 500 <= exc.code < 600 and attempt < retries:
                time.sleep(0.2 * (2**attempt))
                last_error = TranscriptionError(message or f"HTTP {exc.code}")
                continue
            raise TranscriptionError(message or f"HTTP {exc.code}") from exc
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


def request_multipart_json(
    url: str,
    *,
    body: bytes,
    headers: dict[str, str],
    timeout: float = 60.0,
    retries: int = 2,
) -> Any:
    """POST multipart body and parse JSON response with retries (C2 §7)."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            if exc.code in (401, 403):
                raise AuthenticationError(message or f"HTTP {exc.code}") from exc
            if 500 <= exc.code < 600 and attempt < retries:
                time.sleep(0.2 * (2**attempt))
                last_error = TranscriptionError(message or f"HTTP {exc.code}")
                continue
            raise TranscriptionError(message or f"HTTP {exc.code}") from exc
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


def request_bytes(
    url: str,
    *,
    method: str = "POST",
    body: bytes,
    headers: dict[str, str],
    timeout: float = 60.0,
    retries: int = 2,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method=method,
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            if exc.code in (401, 403):
                raise AuthenticationError(message or f"HTTP {exc.code}") from exc
            if 500 <= exc.code < 600 and attempt < retries:
                time.sleep(0.2 * (2**attempt))
                last_error = TranscriptionError(message or f"HTTP {exc.code}")
                continue
            raise TranscriptionError(message or f"HTTP {exc.code}") from exc
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
