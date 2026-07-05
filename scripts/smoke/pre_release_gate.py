"""Pre-release validation gate — single entry for P6 checklist items."""

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


def _run_step(label: str, cmd: list[str], *, timeout: int = 600) -> int:
    print(f"==> {label}")
    completed = subprocess.run(cmd, cwd=str(ROOT), timeout=timeout, check=False)
    if completed.returncode != 0:
        print(f"FAIL {label} (exit {completed.returncode})", file=sys.stderr)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pre-release gate (CI + tag + optional remote manifest)")
    parser.add_argument("--tag", default="", help="Release tag e.g. v0.2.0")
    parser.add_argument("--build", action="store_true", help="Include STT_AIO_RELEASE_BUILD=1 smoke")
    parser.add_argument("--strict", action="store_true", help="Strict release smoke (implies --build)")
    parser.add_argument("--manifest-url", default="", help="Remote manifest URL to verify after release")
    parser.add_argument("--require-ci-green", action="store_true", help="Require gh build.yml green")
    parser.add_argument("--quick", action="store_true", help="Skip release_checklist_smoke (CI + tag only)")
    args = parser.parse_args(argv)

    py = _python()
    exit_code = 0

    exit_code = max(exit_code, _run_step("verify_ci_workflow", [py, "scripts/smoke/verify_ci_workflow.py"]))
    if args.require_ci_green:
        env = {**os.environ, "STT_AIO_CI_REQUIRE_GREEN": "1"}
        completed = subprocess.run(
            [py, "scripts/smoke/verify_ci_workflow.py"],
            cwd=str(ROOT),
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            exit_code = 1

    tag = args.tag.strip()
    manifest = ROOT / "dist" / "installer" / "build-manifest.json"
    if tag and manifest.is_file():
        exit_code = max(
            exit_code,
            _run_step(
                "verify_release_tag",
                [py, "scripts/release/verify_release_tag.py", "--tag", tag],
            ),
        )
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from scripts.release.github_urls import resolve_github_repository  # noqa: WPS433

        if resolve_github_repository():
            exit_code = max(
                exit_code,
                _run_step(
                    "print_release_config",
                    [py, "scripts/release/print_release_config.py", "--tag", tag],
                ),
            )
        else:
            print("skip: print_release_config (no GITHUB_REPOSITORY or git origin)")

    manifest_url = args.manifest_url.strip() or os.environ.get("STT_AIO_MANIFEST_URL", "").strip()
    if manifest_url:
        cmd = [py, "scripts/release/verify_remote_manifest.py", "--url", manifest_url]
        if tag:
            bare = tag.lstrip("vV")
            cmd.extend(["--expected-version", bare])
        exit_code = max(exit_code, _run_step("verify_remote_manifest", cmd))

    smoke_env = dict(os.environ)
    if args.strict:
        smoke_env["STT_AIO_RELEASE_STRICT"] = "1"
        smoke_env["STT_AIO_RELEASE_BUILD"] = "1"
    elif args.build:
        smoke_env["STT_AIO_RELEASE_BUILD"] = "1"
    if tag:
        smoke_env["STT_AIO_RELEASE_TAG"] = tag

    if args.quick:
        print("==> release_checklist_smoke (skipped: --quick)")
        return exit_code

    print("==> release_checklist_smoke")
    completed = subprocess.run(
        [py, "scripts/smoke/release_checklist_smoke.py"],
        cwd=str(ROOT),
        env=smoke_env,
        timeout=3600,
        check=False,
    )
    if completed.returncode != 0:
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
