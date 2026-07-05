"""Validate .github/workflows/build.yml matches release checklist expectations (P6)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
COMPOSITE_ACTION = ROOT / ".github" / "actions" / "windows-build-smoke" / "action.yml"
COMPOSITE_REFERENCE = "./.github/actions/windows-build-smoke"

COMPOSITE_FRAGMENTS: tuple[str, ...] = (
    "python-version:",
    "pytest",
    "--ignore=tests/ui",
    "tests/remote",
    "ko_wer",
    "build/build.py --portable",
    "bundle_smoke.ps1",
    "build/build.py --installer",
    "installer_smoke.ps1",
    "verify_installer.py",
)

BUILD_WORKFLOW_FRAGMENTS: tuple[str, ...] = (
    COMPOSITE_REFERENCE,
    "generate_update_manifest.py",
    "verify_ci_workflow.py",
    "upload-artifact",
)

RELEASE_WORKFLOW_FRAGMENTS: tuple[str, ...] = (
    COMPOSITE_REFERENCE,
    "prepare_release_manifest.py",
    "--github-release",
    "verify_release_tag.py",
    "action-gh-release",
    "generate_update_manifest.py --verify-only",
    "verify_ci_workflow.py",
)


def verify_composite_action() -> list[str]:
    failures: list[str] = []
    if not COMPOSITE_ACTION.is_file():
        return [f"missing composite action: {COMPOSITE_ACTION}"]
    text = COMPOSITE_ACTION.read_text(encoding="utf-8")
    for fragment in COMPOSITE_FRAGMENTS:
        if fragment not in text:
            failures.append(f"windows-build-smoke action missing fragment: {fragment!r}")
    return failures


def verify_workflow_file() -> list[str]:
    failures = verify_composite_action()
    if not WORKFLOW.is_file():
        return failures + [f"missing workflow: {WORKFLOW}"]
    text = WORKFLOW.read_text(encoding="utf-8")
    for fragment in BUILD_WORKFLOW_FRAGMENTS:
        if fragment not in text:
            failures.append(f"build.yml missing required step/fragment: {fragment!r}")
    if "--allow-placeholder" not in text and "STT_AIO_UPDATE_DOWNLOAD_URL" not in text:
        failures.append(
            "generate_update_manifest step must use --allow-placeholder or STT_AIO_UPDATE_DOWNLOAD_URL"
        )
    if "verify_update_manifest" not in text and "--verify-only" not in text:
        failures.append("build.yml should verify update-manifest after generation")
    return failures


def verify_release_workflow_file() -> list[str]:
    failures: list[str] = []
    if not RELEASE_WORKFLOW.is_file():
        return [f"missing workflow: {RELEASE_WORKFLOW}"]
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    for fragment in RELEASE_WORKFLOW_FRAGMENTS:
        if fragment not in text:
            failures.append(f"release.yml missing required fragment: {fragment!r}")
    return failures


def verify_github_run_status() -> tuple[str, str]:
    """Latest build.yml workflow conclusion via gh CLI. Returns (status, detail)."""
    return _verify_github_workflow_run("build.yml")


def verify_release_github_run_status() -> tuple[str, str]:
    """Latest release.yml workflow conclusion via gh CLI."""
    return _verify_github_workflow_run("release.yml")


def _verify_github_workflow_run(workflow_file: str) -> tuple[str, str]:
    """Latest workflow conclusion via gh CLI. Returns (status, detail)."""
    try:
        completed = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                workflow_file,
                "--limit",
                "1",
                "--json",
                "conclusion,status,url",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "skip", "gh CLI not available"

    if completed.returncode != 0:
        return "skip", (completed.stderr or completed.stdout or "gh run list failed").strip()

    try:
        rows = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return "skip", "gh output not JSON"

    if not rows:
        return "skip", "no workflow runs found"

    row = rows[0]
    status = row.get("status", "")
    conclusion = row.get("conclusion") or ""
    url = row.get("url", "")
    if status != "completed":
        return "pending", f"latest run in progress ({url})".strip()
    if conclusion == "success":
        return "pass", url or "success"
    return "fail", f"conclusion={conclusion} {url}".strip()


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    failures = verify_workflow_file()
    failures.extend(verify_release_workflow_file())
    workflow_ok = not failures
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
    else:
        print(f"OK workflow file: {WORKFLOW.relative_to(ROOT)}")
        print(f"OK workflow file: {RELEASE_WORKFLOW.relative_to(ROOT)}")
        print(f"OK composite action: {COMPOSITE_ACTION.relative_to(ROOT)}")

    gh_status, gh_detail = verify_github_run_status()
    print(f"github_run={gh_status}: {gh_detail}")

    rel_status, rel_detail = verify_release_github_run_status()
    print(f"release_github_run={rel_status}: {rel_detail}")

    require_green = _env_flag("STT_AIO_CI_REQUIRE_GREEN")
    exit_code = 0
    if not workflow_ok:
        exit_code = 1
    if gh_status == "fail":
        exit_code = 1
    if rel_status == "fail":
        exit_code = 1
    if require_green and gh_status not in {"pass"}:
        print(
            f"FAIL STT_AIO_CI_REQUIRE_GREEN=1 but github_run={gh_status}",
            file=sys.stderr,
        )
        exit_code = 1
    if require_green and _env_flag("STT_AIO_CI_REQUIRE_RELEASE_GREEN") and rel_status not in {"pass"}:
        print(
            f"FAIL STT_AIO_CI_REQUIRE_RELEASE_GREEN=1 but release_github_run={rel_status}",
            file=sys.stderr,
        )
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
