"""Print post-release app config snippet for update.manifest_url (P6 #11)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD_MANIFEST = ROOT / "dist" / "installer" / "build-manifest.json"


def read_version(build_manifest: Path) -> str:
    payload = json.loads(build_manifest.read_text(encoding="utf-8"))
    version = str(payload.get("version", "")).strip()
    if not version:
        raise ValueError("build-manifest.json missing version")
    return version


def resolve_tag(explicit: str, version: str) -> str:
    tag = explicit.strip() or f"v{version.lstrip('vV')}"
    return tag if tag.startswith("v") else f"v{tag}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print update.manifest_url and release URLs after GitHub Release"
    )
    parser.add_argument("--build-manifest", type=Path, default=DEFAULT_BUILD_MANIFEST)
    parser.add_argument("--tag", default="", help="Release tag (default: v{manifest version})")
    parser.add_argument("--github-repo", default="", help="owner/repo (default: GITHUB_REPOSITORY)")
    args = parser.parse_args(argv)

    if not args.build_manifest.is_file():
        print(f"FAIL build manifest not found: {args.build_manifest}", file=sys.stderr)
        return 1

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from scripts.release.github_urls import (  # noqa: WPS433
        github_release_download_url,
        github_release_manifest_url,
        resolve_github_repository,
    )
    from scripts.release.verify_release_tag import verify_release_tag  # noqa: WPS433

    version = read_version(args.build_manifest)
    tag = resolve_tag(args.tag, version)
    failures = verify_release_tag(tag, args.build_manifest)
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        return 1

    repo = resolve_github_repository(args.github_repo.strip() or None)
    if not repo:
        print("FAIL set --github-repo or GITHUB_REPOSITORY", file=sys.stderr)
        return 1

    manifest_url = github_release_manifest_url(repo, tag)
    download_url = github_release_download_url(repo, tag)

    print(f"version={version}")
    print(f"tag={tag}")
    print(f"manifest_url={manifest_url}")
    print(f"download_url={download_url}")
    print()
    print("# App settings (설정 → 일반 → 매니페스트 URL)")
    print(f"update.manifest_url={manifest_url}")
    print("update.auto_check=true")
    print()
    print("# Verify after release upload:")
    print(f"curl -fsSL {manifest_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
