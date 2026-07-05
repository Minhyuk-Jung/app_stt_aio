"""Post-build bundle verification (C16 plan §6.2, §10)."""

from __future__ import annotations

from pathlib import Path

REQUIRED_EXE = "STT-AIO.exe"
MODEL_NAME_MARKERS = (
    "faster-whisper-",
    "whisper-large",
    "whisper-medium",
    "whisper-small",
    "systran",
    "model.bin",
    "ggml",
)
MIN_SUSPICIOUS_MODEL_BYTES = 5 * 1024 * 1024


def _find_qt_platform_plugin(app_dir: Path) -> Path | None:
    for path in app_dir.rglob("qwindows.dll"):
        if path.is_file():
            return path
    return None


def _find_pwa_index(app_dir: Path) -> Path | None:
    for path in app_dir.rglob("index.html"):
        if path.is_file() and "remote" in path.parts and "pwa" in path.parts:
            return path
    return None


def verify_app_bundle(app_dir: Path) -> list[str]:
    """Return human-readable failures; empty list means OK."""
    failures: list[str] = []
    if not app_dir.is_dir():
        return [f"bundle directory not found: {app_dir}"]

    exe = app_dir / REQUIRED_EXE
    if not exe.is_file():
        failures.append(f"missing executable: {REQUIRED_EXE}")

    if _find_qt_platform_plugin(app_dir) is None:
        failures.append(
            "missing Qt platform plugin (qwindows.dll); "
            "rebuild with collect_all('PySide6') in pyinstaller.spec"
        )

    if _find_pwa_index(app_dir) is None:
        failures.append(
            "missing remote PWA (remote/gateway/pwa/index.html); "
            "add PWA datas to pyinstaller.spec (C16 P4)"
        )

    for path in app_dir.rglob("*"):
        if not path.is_file():
            continue
        lowered = path.name.lower()
        if any(marker in lowered for marker in MODEL_NAME_MARKERS):
            size = path.stat().st_size
            if size >= MIN_SUSPICIOUS_MODEL_BYTES:
                rel = path.relative_to(app_dir)
                failures.append(f"suspected Whisper model bundled: {rel} ({size} bytes)")

    return failures


def main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Verify STT-AIO app bundle (C16)")
    parser.add_argument(
        "--app-dir",
        type=Path,
        default=Path("dist") / "STT-AIO",
        help="PyInstaller onedir output directory",
    )
    args = parser.parse_args()
    failures = verify_app_bundle(args.app_dir.resolve())
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    print(f"verify_bundle_ok dir={args.app_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
