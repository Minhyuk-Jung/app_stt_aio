"""C16 packaging orchestration (plan §6.2).

Usage:
  python build/build.py              # PyInstaller onedir
  python build/build.py --portable   # + zip portable bundle
  python build/build.py --installer  # + Inno Setup (ISCC on PATH)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
APP_DIR = DIST_DIR / "STT-AIO"
INSTALLER_DIR = DIST_DIR / "installer"
SPEC = ROOT / "build" / "pyinstaller.spec"
ISS = ROOT / "build" / "installer.iss"
VERSION_INFO = ROOT / "build" / "version_info.txt"
SMARTSCREEN = ROOT / "build" / "SMARTSCREEN.txt"


def _import_version():
    sys.path.insert(0, str(ROOT / "build"))
    try:
        import version as build_version  # noqa: WPS433

        return build_version
    finally:
        sys.path.pop(0)


def generate_version_info() -> Path:
    build_version = _import_version()
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_version_info import write_version_info  # noqa: WPS433

        write_version_info(
            VERSION_INFO,
            version=build_version.VERSION,
            product=build_version.PRODUCT_NAME,
            publisher=build_version.PUBLISHER,
        )
    finally:
        sys.path.pop(0)
    return VERSION_INFO


def verify_bundle() -> None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from verify_bundle import verify_app_bundle  # noqa: WPS433

        failures = verify_app_bundle(APP_DIR)
    finally:
        sys.path.pop(0)
    if failures:
        raise RuntimeError("Bundle verification failed:\n" + "\n".join(failures))


def copy_smartscreen_notice() -> Path:
    if not SMARTSCREEN.is_file():
        raise FileNotFoundError(SMARTSCREEN)
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    dest = INSTALLER_DIR / "SMARTSCREEN.txt"
    shutil.copy2(SMARTSCREEN, dest)
    return dest


def ensure_app_icon() -> Path:
    icon = ROOT / "build" / "assets" / "icon.ico"
    if icon.is_file():
        return icon
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from generate_icon import write_icon  # noqa: WPS433

        return write_icon(icon)
    finally:
        sys.path.pop(0)


def run_pyinstaller() -> Path:
    if not SPEC.is_file():
        raise FileNotFoundError(SPEC)
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from build_env import pyinstaller_env_error, resolve_build_python  # noqa: WPS433

        env_error = pyinstaller_env_error()
        if env_error:
            raise RuntimeError(env_error)
        py_exe = resolve_build_python()
    finally:
        sys.path.pop(0)
    generate_version_info()
    ensure_app_icon()
    subprocess.check_call(
        [py_exe, "-m", "PyInstaller", str(SPEC), "--noconfirm", "--clean"],
        cwd=str(ROOT),
    )
    exe = APP_DIR / "STT-AIO.exe"
    if not exe.is_file():
        raise RuntimeError(f"PyInstaller output missing: {exe}")
    verify_bundle()
    write_app_version_file()
    copy_smartscreen_notice()
    return exe


def write_app_version_file() -> Path:
    """Write VERSION.txt beside the frozen exe (C16 smoke + runtime version)."""
    build_version = _import_version()
    path = APP_DIR / "VERSION.txt"
    path.write_text(f"{build_version.VERSION}\n", encoding="utf-8")
    return path


def load_existing_artifacts() -> dict[str, dict[str, str]]:
    manifest_path = INSTALLER_DIR / "build-manifest.json"
    if not manifest_path.is_file():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        str(item["type"]): item
        for item in payload.get("artifacts", [])
        if isinstance(item, dict) and "type" in item
    }


def merge_artifacts(new_artifacts: list[dict[str, str]]) -> list[dict[str, str]]:
    """Merge new build artifacts into any existing manifest (skip-pyinstaller safe)."""
    merged = load_existing_artifacts()
    for item in new_artifacts:
        merged[item["type"]] = item
    return list(merged.values())


def finalize_manifest(artifacts: list[dict[str, str]]) -> Path:
    merged = merge_artifacts(artifacts)
    manifest = write_manifest(artifacts=merged)
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from verify_installer import verify_build_manifest  # noqa: WPS433

        failures = verify_build_manifest(manifest)
    finally:
        sys.path.pop(0)
    if failures:
        raise RuntimeError("Manifest verification failed:\n" + "\n".join(failures))
    return manifest


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(*, artifacts: list[dict[str, str]]) -> Path:
    build_version = _import_version()
    manifest = {
        "product": build_version.PRODUCT_NAME,
        "version": build_version.VERSION,
        "bundle_models": build_version.BUNDLE_MODELS,
        "artifacts": artifacts,
    }
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    path = INSTALLER_DIR / "build-manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def build_portable_zip() -> Path:
    build_version = _import_version()
    if not APP_DIR.is_dir():
        raise RuntimeError("Run PyInstaller before creating portable zip")
    zip_path = DIST_DIR / f"STT-AIO-portable-{build_version.VERSION}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(APP_DIR.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(APP_DIR.parent).as_posix())
    return zip_path


def build_installer(*, require: bool = False) -> Path | None:
    sys.path.insert(0, str(ROOT / "build"))
    try:
        from find_iscc import find_iscc  # noqa: WPS433

        iscc_path = find_iscc()
    finally:
        sys.path.pop(0)
    if iscc_path is None:
        message = "Inno Setup compiler (ISCC) not found — skipping installer."
        if require:
            raise RuntimeError(
                f"{message} Install Inno Setup 6 or add ISCC to PATH "
                "(winget install JRSoftware.InnoSetup)."
            )
        print(message, file=sys.stderr)
        return None
    if not APP_DIR.is_dir():
        raise RuntimeError("Run PyInstaller before building installer")
    build_version = _import_version()
    subprocess.check_call(
        [str(iscc_path), f"/DMyAppVersion={build_version.VERSION}", str(ISS)],
        cwd=str(ROOT / "build"),
    )
    setup = INSTALLER_DIR / f"STT-AIO-Setup-{build_version.VERSION}.exe"
    if not setup.is_file():
        candidates = list(INSTALLER_DIR.glob("STT-AIO-Setup-*.exe"))
        if not candidates:
            raise RuntimeError("Inno Setup did not produce STT-AIO-Setup-*.exe")
        setup = candidates[0]

    sys.path.insert(0, str(ROOT / "build"))
    try:
        from verify_installer import verify_installer_artifact  # noqa: WPS433

        failures = verify_installer_artifact(setup)
    finally:
        sys.path.pop(0)
    if failures:
        raise RuntimeError("Installer verification failed:\n" + "\n".join(failures))
    return setup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="STT-AIO packaging (C16)")
    parser.add_argument("--portable", action="store_true", help="Create portable zip after PyInstaller")
    parser.add_argument("--installer", action="store_true", help="Run Inno Setup after PyInstaller")
    parser.add_argument(
        "--require-installer",
        action="store_true",
        help="Fail if Inno Setup (ISCC) is missing when --installer is set",
    )
    parser.add_argument("--skip-pyinstaller", action="store_true", help="Only run post-steps")
    args = parser.parse_args(argv)

    artifacts: list[dict[str, str]] = []

    if not args.skip_pyinstaller:
        exe = run_pyinstaller()
        artifacts.append({"type": "app", "path": str(exe.relative_to(ROOT)), "sha256": sha256_file(exe)})

    if args.portable:
        portable = build_portable_zip()
        artifacts.append(
            {"type": "portable", "path": str(portable.relative_to(ROOT)), "sha256": sha256_file(portable)}
        )

    if args.installer:
        setup = build_installer(require=args.require_installer)
        if setup is not None:
            artifacts.append(
                {"type": "installer", "path": str(setup.relative_to(ROOT)), "sha256": sha256_file(setup)}
            )

    if artifacts:
        manifest = finalize_manifest(artifacts)
        print(f"Manifest: {manifest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
