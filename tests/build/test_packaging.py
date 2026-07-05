"""C16 packaging policy and version tests."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_version_matches_core() -> None:
    from core.version import get_version

    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert match is not None
    assert get_version() == match.group(1)


def test_build_version_matches_pyproject() -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        import version as build_version  # noqa: WPS433
    finally:
        sys.path.pop(0)
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert build_version.VERSION == match.group(1)


def test_models_not_bundled_policy() -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        import version as build_version  # noqa: WPS433
    finally:
        sys.path.pop(0)
    assert build_version.BUNDLE_MODELS is False


def test_pyinstaller_spec_excludes_whisper_model_dirs() -> None:
    spec = (ROOT / "build" / "pyinstaller.spec").read_text(encoding="utf-8")
    assert "faster-whisper" in spec or "faster_whisper" in spec
    assert "models" not in spec.lower() or "bundle_models" not in spec.lower()
    assert "Systran" not in spec


def test_pyinstaller_spec_includes_migrations_and_version() -> None:
    spec = (ROOT / "build" / "pyinstaller.spec").read_text(encoding="utf-8")
    assert "core.store.migrations.v001_initial" in spec
    assert "version_info.txt" in spec
    assert "collect_all" in spec
    assert "PySide6" in spec
    assert "remote/gateway/pwa" in spec


def test_installer_iss_mentions_model_download() -> None:
    iss = (ROOT / "build" / "installer.iss").read_text(encoding="utf-8")
    assert "모델" in iss or "model" in iss.lower()
    assert "dist\\STT-AIO" in iss or "dist/STT-AIO" in iss


def test_installer_iss_upgrade_and_previous_dir() -> None:
    iss = (ROOT / "build" / "installer.iss").read_text(encoding="utf-8")
    assert "UsePreviousAppDir=yes" in iss
    assert "SMARTSCREEN.txt" in iss
    assert "APPDATA" in iss


def test_smartscreen_notice_exists() -> None:
    path = ROOT / "build" / "SMARTSCREEN.txt"
    text = path.read_text(encoding="utf-8")
    assert "SmartScreen" in text
    assert "APPDATA" in text


def test_requirements_ci_pins_pyinstaller() -> None:
    text = (ROOT / "build" / "requirements-ci.txt").read_text(encoding="utf-8")
    assert "pyinstaller==" in text


def test_build_script_runs_verify_and_version_info() -> None:
    text = (ROOT / "build" / "build.py").read_text(encoding="utf-8")
    assert "generate_version_info" in text
    assert "verify_bundle" in text
    assert "copy_smartscreen_notice" in text


def test_generate_version_info_writes_file(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_version_info import write_version_info  # noqa: WPS433

        out = tmp_path / "version_info.txt"
        write_version_info(out, version="1.2.3", product="STT-AIO", publisher="STT-AIO")
        content = out.read_text(encoding="utf-8")
        assert "1.2.3" in content
        assert "STT-AIO" in content
        assert "VSVersionInfo" in content
    finally:
        sys.path.pop(0)


def test_verify_bundle_ok_without_models(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from verify_bundle import verify_app_bundle  # noqa: WPS433

        app_dir = tmp_path / "STT-AIO"
        app_dir.mkdir()
        (app_dir / "STT-AIO.exe").write_bytes(b"MZ")
        (app_dir / "_internal" / "PySide6" / "plugins" / "platforms").mkdir(
            parents=True,
        )
        (app_dir / "_internal" / "PySide6" / "plugins" / "platforms" / "qwindows.dll").write_bytes(
            b"MZ",
        )
        (app_dir / "_internal" / "remote" / "gateway" / "pwa").mkdir(parents=True)
        (app_dir / "_internal" / "remote" / "gateway" / "pwa" / "index.html").write_text(
            "<html></html>",
            encoding="utf-8",
        )
        assert verify_app_bundle(app_dir) == []
    finally:
        sys.path.pop(0)


def test_verify_bundle_catches_large_model_file(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from verify_bundle import verify_app_bundle  # noqa: WPS433

        app_dir = tmp_path / "STT-AIO"
        app_dir.mkdir()
        (app_dir / "STT-AIO.exe").write_bytes(b"MZ")
        (app_dir / "_internal" / "PySide6" / "plugins" / "platforms").mkdir(
            parents=True,
        )
        (app_dir / "_internal" / "PySide6" / "plugins" / "platforms" / "qwindows.dll").write_bytes(
            b"MZ",
        )
        (app_dir / "_internal" / "remote" / "gateway" / "pwa").mkdir(parents=True)
        (app_dir / "_internal" / "remote" / "gateway" / "pwa" / "index.html").write_text(
            "<html></html>",
            encoding="utf-8",
        )
        model = app_dir / "faster-whisper-small.bin"
        model.write_bytes(b"x" * (6 * 1024 * 1024))
        failures = verify_app_bundle(app_dir)
        assert len(failures) == 1
        assert "faster-whisper-small.bin" in failures[0]
    finally:
        sys.path.pop(0)


def test_verify_bundle_catches_missing_qt_platform_plugin(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from verify_bundle import verify_app_bundle  # noqa: WPS433

        app_dir = tmp_path / "STT-AIO"
        app_dir.mkdir()
        (app_dir / "STT-AIO.exe").write_bytes(b"MZ")
        failures = verify_app_bundle(app_dir)
        assert any("qwindows.dll" in line for line in failures)
    finally:
        sys.path.pop(0)


def test_runtime_helpers() -> None:
    from core.runtime import bundle_root, is_frozen, startup_failure_message

    assert is_frozen() is False
    assert bundle_root() is None
    msg = startup_failure_message(RuntimeError("boom"))
    assert "boom" in msg
    assert "logs" in msg.lower()


def test_diagnostics_uses_core_version() -> None:
    from core.diagnostics.diagnostics import APP_VERSION
    from core.version import get_version

    assert APP_VERSION == get_version()


def test_find_iscc_returns_path_or_none() -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from find_iscc import find_iscc  # noqa: WPS433

        path = find_iscc()
        if path is not None:
            assert path.name.lower() == "iscc.exe"
            assert path.is_file()
    finally:
        sys.path.pop(0)


def test_verify_installer_artifact_rejects_small_file(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from verify_installer import verify_installer_artifact  # noqa: WPS433

        setup = tmp_path / "STT-AIO-Setup-0.1.0.exe"
        setup.write_bytes(b"tiny")
        failures = verify_installer_artifact(setup)
        assert failures
        assert "too small" in failures[0]
    finally:
        sys.path.pop(0)


def test_verify_build_manifest_ok(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from verify_installer import verify_build_manifest  # noqa: WPS433

        manifest = tmp_path / "build-manifest.json"
        manifest.write_text(
            '{"product":"STT-AIO","version":"0.1.0","artifacts":[{"type":"app","path":"dist/x","sha256":"abc"}]}',
            encoding="utf-8",
        )
        assert verify_build_manifest(manifest) == []
    finally:
        sys.path.pop(0)


def test_build_script_supports_require_installer_flag() -> None:
    text = (ROOT / "build" / "build.py").read_text(encoding="utf-8")
    assert "--require-installer" in text
    assert "find_iscc" in text
    assert "merge_artifacts" in text
    assert "finalize_manifest" in text


def test_merge_artifacts_preserves_existing_types(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "stt_build",
        ROOT / "build" / "build.py",
    )
    assert spec and spec.loader
    build_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_mod)

    build_mod.INSTALLER_DIR = tmp_path / "installer"
    build_mod.INSTALLER_DIR.mkdir(parents=True)
    manifest = build_mod.INSTALLER_DIR / "build-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "product": "STT-AIO",
                "version": "0.1.0",
                "artifacts": [
                    {
                        "type": "app",
                        "path": "dist/STT-AIO/STT-AIO.exe",
                        "sha256": "abc",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    merged = build_mod.merge_artifacts(
        [
            {
                "type": "installer",
                "path": "dist/installer/STT-AIO-Setup-0.1.0.exe",
                "sha256": "def",
            }
        ]
    )
    types = {item["type"] for item in merged}
    assert types == {"app", "installer"}


def test_get_version_reads_version_txt_when_frozen(tmp_path: Path, monkeypatch) -> None:
    from core import version as core_version

    core_version.get_version.cache_clear()
    exe = tmp_path / "STT-AIO.exe"
    exe.write_bytes(b"MZ")
    version_file = tmp_path / "VERSION.txt"
    version_file.write_text("9.8.7\n", encoding="utf-8")

    monkeypatch.setattr("core.runtime.is_frozen", lambda: True)
    monkeypatch.setattr(core_version.sys, "executable", str(exe))

    assert core_version.get_version() == "9.8.7"
    core_version.get_version.cache_clear()
