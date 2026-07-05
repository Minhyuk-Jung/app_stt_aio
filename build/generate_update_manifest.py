"""Generate C22 update manifest from build-manifest.json (P5 release).

Usage:
  python build/generate_update_manifest.py
  python build/generate_update_manifest.py --download-url https://github.com/OWNER/repo/releases/download/v0.2.0/STT-AIO-Setup-0.2.0.exe
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD_MANIFEST = ROOT / "dist" / "installer" / "build-manifest.json"
DEFAULT_OUTPUT = ROOT / "dist" / "installer" / "update-manifest.json"
PLACEHOLDER_HOSTS = frozenset({"example.com", "www.example.com"})
PLACEHOLDER_MARKERS = ("placeholder", "changeme")


def is_placeholder_download_url(url: str) -> bool:
    lowered = url.lower().strip()
    if not lowered:
        return True
    if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
        return True
    host = (urlparse(lowered).hostname or "").lower()
    return host in PLACEHOLDER_HOSTS


def verify_update_manifest(manifest_path: Path, *, allow_placeholder: bool = False) -> list[str]:
    """Return human-readable failures; empty list means OK."""
    failures: list[str] = []
    if not manifest_path.is_file():
        return [f"update manifest not found: {manifest_path}"]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid update manifest JSON: {exc}"]

    for key in ("version", "download_url", "checksum_sha256"):
        if key not in payload:
            failures.append(f"update manifest missing key: {key}")
    url = str(payload.get("download_url", ""))
    if url and not url.lower().startswith("https://"):
        failures.append("download_url must use HTTPS")
    checksum = str(payload.get("checksum_sha256", ""))
    if len(checksum) != 64 or not all(c in "0123456789abcdef" for c in checksum.lower()):
        failures.append("checksum_sha256 must be 64 hex chars")
    if not allow_placeholder and is_placeholder_download_url(url):
        failures.append(
            "download_url is placeholder — set STT_AIO_UPDATE_DOWNLOAD_URL or pass --download-url"
        )
    return failures


def _installer_artifact(payload: dict) -> dict | None:
    for item in payload.get("artifacts", []):
        if isinstance(item, dict) and item.get("type") == "installer":
            return item
    return None


def build_update_manifest(
    build_manifest: dict,
    *,
    download_url: str,
    release_notes: str = "",
    mandatory: bool = False,
) -> dict:
    version = str(build_manifest.get("version", ""))
    installer = _installer_artifact(build_manifest)
    if installer is None:
        raise ValueError("build-manifest.json has no installer artifact")
    checksum = installer.get("sha256")
    if not checksum:
        raise ValueError("installer artifact missing sha256")
    notes = release_notes or f"STT-AIO {version} release"
    return {
        "version": version,
        "download_url": download_url,
        "checksum_sha256": checksum,
        "release_notes": notes,
        "mandatory": mandatory,
        "notes_by_version": {version: notes},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate C22 update-manifest.json from build output")
    parser.add_argument("--build-manifest", type=Path, default=DEFAULT_BUILD_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--download-url", default="", help="Public HTTPS URL for the installer exe")
    parser.add_argument("--release-notes", default="")
    parser.add_argument("--mandatory", action="store_true")
    parser.add_argument(
        "--allow-placeholder",
        action="store_true",
        help="Allow example.com placeholder URL (dev only)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing manifest at --output (no generation)",
    )
    args = parser.parse_args(argv)

    if args.verify_only:
        failures = verify_update_manifest(args.output, allow_placeholder=args.allow_placeholder)
        if failures:
            for line in failures:
                print(f"FAIL {line}", file=sys.stderr)
            return 1
        print(f"OK {args.output}")
        return 0

    if not args.build_manifest.is_file():
        print(f"FAIL build manifest not found: {args.build_manifest}", file=sys.stderr)
        return 1

    payload = json.loads(args.build_manifest.read_text(encoding="utf-8"))
    version = payload.get("version", "0.0.0")
    download_url = args.download_url.strip()
    if not download_url:
        import os

        download_url = os.environ.get("STT_AIO_UPDATE_DOWNLOAD_URL", "").strip()
    if not download_url:
        download_url = f"https://example.com/STT-AIO-Setup-{version}.exe"

    try:
        update = build_update_manifest(
            payload,
            download_url=download_url,
            release_notes=args.release_notes,
            mandatory=args.mandatory,
        )
    except ValueError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(update, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failures = verify_update_manifest(args.output, allow_placeholder=args.allow_placeholder)
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
