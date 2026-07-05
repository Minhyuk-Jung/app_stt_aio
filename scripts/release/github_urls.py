"""GitHub Releases URL helpers for C22 update manifest (P6 #11)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_GITHUB_REPO_RE = re.compile(
    r"(?:https?://|git@)github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)"
)


def normalize_tag(version: str) -> str:
    version = version.strip()
    return version if version.startswith("v") else f"v{version}"


def installer_asset_name(version: str) -> str:
    bare = version.lstrip("vV")
    return f"STT-AIO-Setup-{bare}.exe"


def github_release_download_url(
    repo: str,
    version: str,
    *,
    asset_name: str | None = None,
) -> str:
    """HTTPS URL for an asset attached to a GitHub Release."""
    repo = repo.strip().strip("/")
    if not re.fullmatch(r"[^/]+/[^/]+", repo):
        raise ValueError(f"invalid github repo: {repo!r}")
    tag = normalize_tag(version)
    asset = asset_name or installer_asset_name(version)
    return f"https://github.com/{repo}/releases/download/{tag}/{asset}"


def github_release_manifest_url(repo: str, version: str) -> str:
    tag = normalize_tag(version)
    repo = repo.strip().strip("/")
    return f"https://github.com/{repo}/releases/download/{tag}/update-manifest.json"


def parse_github_repository(remote_url: str) -> str | None:
    match = _GITHUB_REPO_RE.search(remote_url.strip())
    if not match:
        return None
    return f"{match.group('owner')}/{match.group('repo')}"


def resolve_github_repository_from_git(cwd: Path | None = None) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(cwd or ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if completed.returncode != 0:
        return None
    return parse_github_repository((completed.stdout or "").strip())


def resolve_github_repository(explicit: str | None = None) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    env = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if env:
        return env
    return resolve_github_repository_from_git()
