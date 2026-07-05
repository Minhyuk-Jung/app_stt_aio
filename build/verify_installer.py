"""Post-build installer verification (C16 plan §10)."""

from __future__ import annotations

import json
from pathlib import Path

MIN_SETUP_BYTES = 256 * 1024


def verify_installer_artifact(setup_exe: Path) -> list[str]:
    """Return human-readable failures; empty list means OK."""
    failures: list[str] = []
    if not setup_exe.is_file():
        return [f"installer not found: {setup_exe}"]
    size = setup_exe.stat().st_size
    if size < MIN_SETUP_BYTES:
        failures.append(f"installer too small: {setup_exe.name} ({size} bytes)")
    if not setup_exe.name.startswith("STT-AIO-Setup-"):
        failures.append(f"unexpected installer name: {setup_exe.name}")
    if setup_exe.suffix.lower() != ".exe":
        failures.append(f"installer must be .exe: {setup_exe.name}")
    return failures


def verify_build_manifest(manifest_path: Path) -> list[str]:
    """Validate build-manifest.json shape produced by build.py."""
    failures: list[str] = []
    if not manifest_path.is_file():
        return [f"manifest not found: {manifest_path}"]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid manifest JSON: {exc}"]

    for key in ("product", "version", "artifacts"):
        if key not in payload:
            failures.append(f"manifest missing key: {key}")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        failures.append("manifest artifacts must be a list")
        return failures
    for item in artifacts:
        if not isinstance(item, dict):
            failures.append("manifest artifact entry must be an object")
            continue
        for key in ("type", "path", "sha256"):
            if key not in item:
                failures.append(f"manifest artifact missing {key}")
    return failures


def main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Verify STT-AIO installer output (C16)")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "build"))
    try:
        import version as build_version  # noqa: WPS433

        default_setup = (
            root / "dist" / "installer" / f"STT-AIO-Setup-{build_version.VERSION}.exe"
        )
    finally:
        sys.path.pop(0)

    parser.add_argument(
        "--setup",
        type=Path,
        default=default_setup,
        help="Inno Setup output executable",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("dist") / "installer" / "build-manifest.json",
        help="build-manifest.json path",
    )
    args = parser.parse_args()

    failures: list[str] = []
    failures.extend(verify_installer_artifact(args.setup.resolve()))
    failures.extend(verify_build_manifest(args.manifest.resolve()))
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    print(f"verify_installer_ok setup={args.setup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
