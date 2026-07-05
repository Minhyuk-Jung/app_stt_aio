"""Tests for scripts/release/github_urls.py."""

from __future__ import annotations

import pytest

from scripts.release.github_urls import (
    github_release_download_url,
    github_release_manifest_url,
    installer_asset_name,
    normalize_tag,
    parse_github_repository,
    resolve_github_repository,
)


def test_parse_github_repository() -> None:
    assert parse_github_repository("https://github.com/acme/stt-aio.git") == "acme/stt-aio"
    assert parse_github_repository("git@github.com:acme/stt-aio.git") == "acme/stt-aio"
    assert parse_github_repository("https://gitlab.com/acme/stt") is None


def test_normalize_tag() -> None:
    assert normalize_tag("0.2.0") == "v0.2.0"
    assert normalize_tag("v1.0.0") == "v1.0.0"


def test_github_release_download_url() -> None:
    url = github_release_download_url("owner/repo", "0.2.0")
    assert url == "https://github.com/owner/repo/releases/download/v0.2.0/STT-AIO-Setup-0.2.0.exe"


def test_github_release_manifest_url() -> None:
    url = github_release_manifest_url("owner/repo", "v0.2.0")
    assert url.endswith("/releases/download/v0.2.0/update-manifest.json")


def test_installer_asset_name() -> None:
    assert installer_asset_name("v0.2.0") == "STT-AIO-Setup-0.2.0.exe"


def test_invalid_repo_raises() -> None:
    with pytest.raises(ValueError):
        github_release_download_url("not-a-repo", "1.0.0")


def test_resolve_github_repository(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.setattr(
        "scripts.release.github_urls.resolve_github_repository_from_git",
        lambda cwd=None: None,
    )
    assert resolve_github_repository() is None
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/stt-aio")
    assert resolve_github_repository() == "acme/stt-aio"
    assert resolve_github_repository("override/x") == "override/x"
