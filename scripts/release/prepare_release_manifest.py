"""Prepare C22 update-manifest for release hosting (P6 #11)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD_MANIFEST = ROOT / "dist" / "installer" / "build-manifest.json"
DEFAULT_OUTPUT = ROOT / "dist" / "installer" / "update-manifest.json"


def _load_generate_main():
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_update_manifest import main as gen_main  # noqa: WPS433
        from generate_update_manifest import verify_update_manifest  # noqa: WPS433
    finally:
        sys.path.pop(0)
    return gen_main, verify_update_manifest


def _read_version(build_manifest: Path) -> str:
    payload = json.loads(build_manifest.read_text(encoding="utf-8"))
    return str(payload.get("version", "")).strip()


def resolve_download_url(
    *,
    explicit: str,
    github_release: bool,
    tag: str,
    repo: str | None,
    build_manifest: Path,
) -> str:
    if explicit:
        return explicit
    env_url = os.environ.get("STT_AIO_UPDATE_DOWNLOAD_URL", "").strip()
    if env_url:
        return env_url
    if github_release:
        from scripts.release.github_urls import (  # noqa: WPS433
            github_release_download_url,
            resolve_github_repository,
        )

        repository = resolve_github_repository(repo)
        if not repository:
            raise ValueError("GITHUB_REPOSITORY or --github-repo required with --github-release")
        version = tag.lstrip("vV") if tag else _read_version(build_manifest)
        if tag:
            version_for_url = tag
        else:
            version_for_url = version
        return github_release_download_url(repository, version_for_url)
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare release update-manifest (strict, real URL)")
    parser.add_argument("--build-manifest", type=Path, default=DEFAULT_BUILD_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--download-url", default="", help="Public HTTPS installer URL")
    parser.add_argument("--github-release", action="store_true", help="Build URL from GITHUB_REPOSITORY + tag/version")
    parser.add_argument("--github-repo", default="", help="owner/repo (default: GITHUB_REPOSITORY)")
    parser.add_argument("--tag", default="", help="Release tag e.g. v0.2.0 (for --github-release)")
    parser.add_argument("--release-notes", default="")
    parser.add_argument("--mandatory", action="store_true")
    parser.add_argument("--print-gh-upload", action="store_true")
    args = parser.parse_args(argv)

    if not args.build_manifest.is_file():
        print(f"FAIL build manifest not found: {args.build_manifest}", file=sys.stderr)
        return 1

    if args.tag.strip():
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from scripts.release.verify_release_tag import verify_release_tag  # noqa: WPS433

        tag_failures = verify_release_tag(args.tag.strip(), args.build_manifest)
        if tag_failures:
            for line in tag_failures:
                print(f"FAIL {line}", file=sys.stderr)
            return 1

    try:
        download_url = resolve_download_url(
            explicit=args.download_url.strip(),
            github_release=args.github_release,
            tag=args.tag.strip(),
            repo=args.github_repo.strip() or None,
            build_manifest=args.build_manifest,
        )
    except ValueError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    if not download_url:
        print(
            "FAIL set --download-url, STT_AIO_UPDATE_DOWNLOAD_URL, or --github-release",
            file=sys.stderr,
        )
        return 1

    gen_main, verify_update_manifest = _load_generate_main()
    gen_argv = [
        "--build-manifest",
        str(args.build_manifest),
        "--output",
        str(args.output),
        "--download-url",
        download_url,
    ]
    if args.release_notes:
        gen_argv.extend(["--release-notes", args.release_notes])
    if args.mandatory:
        gen_argv.append("--mandatory")

    code = gen_main(gen_argv)
    if code != 0:
        return code

    failures = verify_update_manifest(args.output, allow_placeholder=False)
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        return 1

    payload = json.loads(args.output.read_text(encoding="utf-8"))
    version = payload.get("version", "?")
    print(f"OK wrote {args.output}")
    print(f"version={version}")
    print(f"download_url={payload.get('download_url')}")
    print(f"checksum_sha256={payload.get('checksum_sha256')}")

    if args.print_gh_upload or args.github_release:
        from scripts.release.github_urls import github_release_manifest_url, resolve_github_repository

        repo = resolve_github_repository(args.github_repo.strip() or None)
        if repo:
            manifest_url = github_release_manifest_url(repo, args.tag or version)
            print(f"manifest_url={manifest_url}")
            print("# Set update.manifest_url in app settings to manifest_url after release upload")

    if args.print_gh_upload:
        setup = args.build_manifest.parent / f"STT-AIO-Setup-{version}.exe"
        print()
        print("# Or use workflow: .github/workflows/release.yml (push tag v*)")
        print(f"gh release create v{version} {setup} {args.output} --title \"STT-AIO {version}\"")
    return 0


if __name__ == "__main__":
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
