"""Tests for scripts/release/post_release_checklist.py."""

from __future__ import annotations

from unittest.mock import patch

from scripts.release.post_release_checklist import main


def test_post_release_checklist_requires_manifest_or_skips_remote() -> None:
    with patch("scripts.release.post_release_checklist._run", return_value=0) as run:
        code = main(["--tag", "v1.0.0"])
    assert code == 0
    assert run.call_count == 1
    assert "print_release_config" in run.call_args_list[0].args[0][1]


def test_post_release_checklist_verifies_remote_manifest() -> None:
    with patch("scripts.release.post_release_checklist._run", return_value=0) as run:
        code = main(
            [
                "--tag",
                "v1.0.0",
                "--manifest-url",
                "https://github.com/acme/r/releases/download/v1.0.0/update-manifest.json",
            ]
        )
    assert code == 0
    assert run.call_count == 2
    assert "verify_remote_manifest" in run.call_args_list[0].args[0][1]
