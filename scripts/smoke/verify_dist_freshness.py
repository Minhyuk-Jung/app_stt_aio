"""Check whether packaged dist/ artifacts are stale vs project version sources (P6)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXE = ROOT / "dist" / "STT-AIO" / "STT-AIO.exe"
DEFAULT_MANIFEST = ROOT / "dist" / "installer" / "build-manifest.json"
STAMP_PATH = ROOT / "dist" / "installer" / "build-stamp.json"
VERSION_SOURCES = (
    ROOT / "pyproject.toml",
    ROOT / "core" / "version.py",
)


def newest_source_mtime() -> float:
    mtimes = [path.stat().st_mtime for path in VERSION_SOURCES if path.is_file()]
    return max(mtimes) if mtimes else 0.0


def read_build_stamp() -> dict | None:
    if not STAMP_PATH.is_file():
        return None
    try:
        payload = json.loads(STAMP_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def write_build_stamp(*, version: str, portable: bool, installer: bool) -> None:
    import platform
    from datetime import datetime, timezone

    STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": version,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "portable": portable,
        "installer": installer,
        "python": platform.python_version(),
        "platform": platform.system(),
    }
    STAMP_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def verify_dist_freshness(
    *,
    exe: Path = DEFAULT_EXE,
    strict: bool = False,
) -> list[str]:
    """Return human-readable failures/warnings; empty means OK."""
    issues: list[str] = []
    if not exe.is_file():
        if strict:
            issues.append(f"packaged exe missing: {exe}")
        return issues

    exe_mtime = exe.stat().st_mtime
    source_mtime = newest_source_mtime()
    if source_mtime and exe_mtime < source_mtime:
        issues.append(
            "dist/STT-AIO/STT-AIO.exe older than pyproject.toml or core/version.py "
            "(run STT_AIO_RELEASE_BUILD=1)"
        )

    stamp = read_build_stamp()
    if stamp is None:
        issues.append("dist/installer/build-stamp.json missing (fresh build not recorded)")
    elif DEFAULT_MANIFEST.is_file():
        try:
            manifest_version = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8")).get("version", "")
            if str(manifest_version).strip() and str(stamp.get("version", "")).strip() != str(manifest_version).strip():
                issues.append(
                    f"build-stamp version {stamp.get('version')!r} != build-manifest {manifest_version!r}"
                )
        except (json.JSONDecodeError, OSError):
            pass

    return issues


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Verify dist/ freshness vs project sources")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any issue")
    args = parser.parse_args(argv)

    issues = verify_dist_freshness(strict=args.strict)
    if not issues:
        print("OK dist freshness")
        return 0
    for line in issues:
        prefix = "FAIL" if args.strict else "WARN"
        print(f"{prefix} {line}", file=sys.stderr)
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
