"""Post-release verification checklist (#11 residual, P6)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _python() -> str:
    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


def _run(cmd: list[str], *, timeout: int = 60) -> int:
    completed = subprocess.run(cmd, cwd=str(ROOT), timeout=timeout, check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify GitHub Release manifest and print app config")
    parser.add_argument("--tag", required=True, help="Release tag e.g. v0.2.0")
    parser.add_argument("--manifest-url", default="", help="Published update-manifest.json URL")
    parser.add_argument("--github-repo", default="", help="owner/repo (default: env/git)")
    args = parser.parse_args(argv)

    py = _python()
    tag = args.tag.strip()
    manifest_url = args.manifest_url.strip() or os.environ.get("STT_AIO_MANIFEST_URL", "").strip()
    exit_code = 0

    if manifest_url:
        bare = tag.lstrip("vV")
        cmd = [
            py,
            "scripts/release/verify_remote_manifest.py",
            "--url",
            manifest_url,
            "--expected-version",
            bare,
        ]
        if _run(cmd) != 0:
            exit_code = 1
    else:
        print("skip: set --manifest-url or STT_AIO_MANIFEST_URL", file=sys.stderr)

    print_cmd = [py, "scripts/release/print_release_config.py", "--tag", tag]
    if args.github_repo.strip():
        print_cmd.extend(["--github-repo", args.github_repo.strip()])
    if _run(print_cmd) != 0:
        exit_code = 1

    if exit_code == 0:
        print("OK post-release checklist")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
