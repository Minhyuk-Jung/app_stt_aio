"""PWA path resolution for dev and frozen bundles."""

from __future__ import annotations

from pathlib import Path

from remote.gateway.app import resolve_pwa_dir


def test_resolve_pwa_dir_points_to_source_tree() -> None:
    pwa = resolve_pwa_dir()
    assert pwa.is_dir()
    assert (pwa / "index.html").is_file()


def test_resolve_pwa_dir_uses_bundle_root_when_frozen(monkeypatch, tmp_path) -> None:
    bundled = tmp_path / "remote" / "gateway" / "pwa"
    bundled.mkdir(parents=True)
    (bundled / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr("core.runtime.is_frozen", lambda: True)
    monkeypatch.setattr("core.runtime.bundle_root", lambda: tmp_path)
    assert resolve_pwa_dir() == bundled
