"""Verify git release tag matches build-manifest.json and installer artifact (P6)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD_MANIFEST = ROOT / "dist" / "installer" / "build-manifest.json"


def tag_to_version(tag: str) -> str:
    return tag.strip().lstrip("vV")


def read_manifest_version(build_manifest: Path) -> str:
    payload = json.loads(build_manifest.read_text(encoding="utf-8"))
    return str(payload.get("version", "")).strip()


def verify_release_tag(tag: str, build_manifest: Path) -> list[str]:
    """Return human-readable failures; empty list means OK."""
    failures: list[str] = []
    tag = tag.strip()
    if not tag:
        return ["release tag is empty"]
    if not build_manifest.is_file():
        return [f"build manifest not found: {build_manifest}"]

    manifest_version = read_manifest_version(build_manifest)
    if not manifest_version:
        failures.append("build-manifest.json missing version")
    elif tag_to_version(tag) != manifest_version:
        failures.append(
            f"tag {tag!r} does not match build-manifest version {manifest_version!r} "
            f"(expected tag v{manifest_version})"
        )

    if manifest_version:
        installer = build_manifest.parent / f"STT-AIO-Setup-{manifest_version}.exe"
        if not installer.is_file():
            failures.append(f"installer artifact missing: {installer.name}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify release tag vs build-manifest.json")
    parser.add_argument("--tag", required=True, help="Release tag e.g. v0.2.0")
    parser.add_argument("--build-manifest", type=Path, default=DEFAULT_BUILD_MANIFEST)
    args = parser.parse_args(argv)

    failures = verify_release_tag(args.tag, args.build_manifest)
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    version = read_manifest_version(args.build_manifest)
    print(f"OK tag {args.tag} matches build-manifest version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
