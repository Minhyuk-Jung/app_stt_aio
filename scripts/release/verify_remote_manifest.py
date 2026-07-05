"""Verify published C22 update manifest URL is reachable and valid (P6 #11)."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def fetch_manifest_payload(url: str, *, timeout: float = 15.0) -> tuple[dict | None, str | None]:
    """Fetch remote manifest JSON. Returns (payload, error_message)."""
    target = url.strip()
    if not target:
        return None, "manifest URL is empty"
    try:
        with urllib.request.urlopen(target, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        payload = json.loads(raw)
    except urllib.error.URLError as exc:
        return None, f"fetch failed: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    except OSError as exc:
        return None, f"fetch failed: {exc}"

    if not isinstance(payload, dict):
        return None, "manifest root must be a JSON object"
    return payload, None


def verify_remote_manifest(
    url: str,
    *,
    expected_version: str | None = None,
    timeout: float = 15.0,
) -> list[str]:
    """Return human-readable failures; empty list means OK."""
    payload, err = fetch_manifest_payload(url, timeout=timeout)
    if err:
        return [err]
    assert payload is not None

    failures: list[str] = []
    if expected_version:
        remote_version = str(payload.get("version", "")).strip()
        if remote_version != expected_version.strip():
            failures.append(
                f"remote version {remote_version!r} != expected {expected_version!r}"
            )

    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_update_manifest import verify_update_manifest  # noqa: WPS433
    finally:
        sys.path.pop(0)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "update-manifest.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        failures.extend(verify_update_manifest(path, allow_placeholder=False))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify remote update-manifest URL (C22 #11)")
    parser.add_argument("url", nargs="?", default="", help="HTTPS manifest URL")
    parser.add_argument("--url", dest="url_flag", default="", help="HTTPS manifest URL")
    parser.add_argument(
        "--expected-version",
        default="",
        help="Optional version to match remote manifest",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    url = (args.url or args.url_flag or "").strip()
    if not url:
        url = __import__("os").environ.get("STT_AIO_MANIFEST_URL", "").strip()
    if not url:
        print("FAIL manifest URL required (arg or STT_AIO_MANIFEST_URL)", file=sys.stderr)
        return 1

    expected = args.expected_version.strip() or None
    failures = verify_remote_manifest(url, expected_version=expected, timeout=args.timeout)
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    print(f"OK remote manifest: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
