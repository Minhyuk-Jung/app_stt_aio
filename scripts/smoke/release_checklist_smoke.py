"""Automate release-checklist items that do not need manual UI (P5 DoD)."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "devplans" / "phases" / "release-checklist-results.md"


def _python() -> str:
    """Prefer project venv for PyInstaller (avoids Anaconda pathlib backport conflict)."""
    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def _run(cmd: list[str], *, timeout: int = 600, env: dict[str, str] | None = None) -> tuple[int, str]:
    completed = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )
    out = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode, out


def _evaluate_nfr_gate() -> tuple[int, str]:
    """Fail release smoke when packaged exe NFR fails (if dist exists)."""
    nfr_path = ROOT / "devplans" / "phases" / "P5-nfr-results.md"
    if not nfr_path.is_file():
        return 0, "skip: run record_nfr_results.py first"

    text = nfr_path.read_text(encoding="utf-8")
    start = text.find("```json")
    end = text.find("```", start + 7) if start >= 0 else -1
    if start < 0 or end < 0:
        return 0, "skip: no JSON block in P5-nfr-results.md"

    raw = text[start + 7 : end].strip()
    if raw.startswith("exit="):
        return 1, raw

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return 1, f"invalid NFR JSON: {exc}"

    packaged = payload.get("idle_cpu_packaged") or {}
    exe = ROOT / "dist" / "STT-AIO" / "STT-AIO.exe"
    if exe.is_file():
        if packaged.get("status") != "ok" or packaged.get("pass") is not True:
            return 1, "packaged idle_cpu/memory NFR failed — see P5-nfr-results.md"
        return 0, "packaged NFR pass"

    dev_idle = payload.get("idle_cpu") or {}
    if dev_idle.get("pass") is False:
        return 0, "dev idle_cpu proxy over target (expected without packaged exe)"
    return 0, "no packaged exe — dev NFR proxy only"


def _run_powershell(script: str, *args: str, timeout: int = 600) -> tuple[int, str]:
    ps_args = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ROOT / "scripts" / "smoke" / script),
        *args,
    ]
    return _run(ps_args, timeout=timeout)


def _record_build_stamp(*, portable: bool, installer: bool) -> None:
    manifest = ROOT / "dist" / "installer" / "build-manifest.json"
    version = "0.0.0"
    if manifest.is_file():
        try:
            version = str(json.loads(manifest.read_text(encoding="utf-8")).get("version", version))
        except (json.JSONDecodeError, OSError):
            pass
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.smoke.verify_dist_freshness import write_build_stamp  # noqa: WPS433

    write_build_stamp(version=version, portable=portable, installer=installer)


def main() -> int:
    today = date.today().isoformat()
    env = f"Python {platform.python_version()} / {platform.system()}"
    py = _python()
    run_build = _env_flag("STT_AIO_RELEASE_BUILD")
    strict = _env_flag("STT_AIO_RELEASE_STRICT") or run_build

    checks: list[tuple[str, int, str]] = []

    code, out = _run([sys.executable, "-m", "pytest", "tests/", "-q", "--ignore=tests/ui"])
    checks.append(("pytest (UI 제외)", code, out))

    ui_env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    ui_code, ui_out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/ui",
            "-q",
            "--ignore=tests/ui/test_end_to_end_offscreen.py",
        ],
        timeout=120,
        env=ui_env,
    )
    checks.append(("pytest UI (offscreen)", ui_code, ui_out))

    code, out = _run(
        [sys.executable, "-m", "pytest", "tests/regression/ko_wer", "-q", "-m", "not integration"],
        timeout=120,
    )
    checks.append(("ko_wer 회귀 (non-integration)", code, out))

    ui_code, ui_out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/updater/test_update_check_logic.py",
            "tests/updater/test_update_check_ui.py",
            "tests/updater/test_update_entry_points.py",
            "tests/updater/test_update_flow_integration.py",
            "-q",
        ],
        timeout=120,
    )
    checks.append(("update_ui_automation", ui_code, ui_out))

    code, out = _run([sys.executable, "scripts/smoke/tunnel_check.py"], timeout=30)
    tunnel_status = "ok" if "status=ok" in out else "skip"
    checks.append(("tunnel_check", 0 if tunnel_status != "fail" else 1, out))

    if run_build:
        code, out = _run([py, "build/build.py", "--portable"], timeout=1800)
        checks.append(("build.py --portable", code, out))
        if code == 0:
            code, out = _run(
                [py, "build/build.py", "--installer", "--skip-pyinstaller", "--require-installer"],
                timeout=600,
            )
            checks.append(("build.py --installer", code, out))
            if code == 0:
                _record_build_stamp(portable=True, installer=True)

    dist = ROOT / "dist" / "STT-AIO"
    if dist.is_dir():
        code, out = _run([py, "build/verify_bundle.py"], timeout=60)
        if code != 0:
            out += "\nhint: run `python build/build.py --portable` or set STT_AIO_RELEASE_BUILD=1"
    elif strict:
        code, out = 1, "FAIL dist/STT-AIO missing (set STT_AIO_RELEASE_BUILD=1)"
    else:
        code, out = 0, "skip: dist/STT-AIO not built (set STT_AIO_RELEASE_BUILD=1 to build)"
    checks.append(("verify_bundle", code, out))

    if dist.is_dir() and code == 0:
        b_code, b_out = _run_powershell("bundle_smoke.ps1", "-RequireExe")
        checks.append(("bundle_smoke", b_code, b_out))

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.smoke.verify_dist_freshness import verify_dist_freshness  # noqa: WPS433

    freshness_issues = verify_dist_freshness(strict=strict)
    if freshness_issues:
        fresh_detail = "warn: " + "; ".join(freshness_issues)
        fresh_code = 1 if strict else 0
    else:
        fresh_detail = "pass"
        fresh_code = 0
    checks.append(("dist_freshness", fresh_code, fresh_detail))

    download_url = os.environ.get("STT_AIO_UPDATE_DOWNLOAD_URL", "").strip()
    release_tag = os.environ.get("STT_AIO_RELEASE_TAG", "").strip()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.release.github_urls import resolve_github_repository  # noqa: WPS433

    manifest = ROOT / "dist" / "installer" / "build-manifest.json"
    update_manifest = ROOT / "dist" / "installer" / "update-manifest.json"
    if manifest.is_file():
        if not release_tag:
            try:
                manifest_version = json.loads(manifest.read_text(encoding="utf-8")).get("version", "")
                if str(manifest_version).strip():
                    release_tag = f"v{str(manifest_version).strip().lstrip('vV')}"
            except (json.JSONDecodeError, OSError):
                release_tag = ""

        if release_tag:
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from scripts.release.verify_release_tag import verify_release_tag  # noqa: WPS433

            tag_failures = verify_release_tag(release_tag, manifest)
            tag_code = 0 if not tag_failures else 1
            tag_out = "pass" if not tag_failures else "\n".join(tag_failures)
            checks.append(("verify_release_tag", tag_code, tag_out))
        elif strict:
            checks.append(("verify_release_tag", 1, "FAIL set STT_AIO_RELEASE_TAG or build manifest version"))
        else:
            checks.append(("verify_release_tag", 0, "skip: no release tag"))

    if manifest.is_file():
        code, out = _run([py, "build/verify_installer.py"], timeout=60)
        if code != 0:
            out += "\nhint: run `python build/build.py --installer` after portable build"
        checks.append(("verify_installer", code, out))

        gen_cmd = [py, "build/generate_update_manifest.py"]
        if download_url:
            gen_cmd.extend(["--download-url", download_url])
        elif not strict:
            gen_cmd.append("--allow-placeholder")
        gen_code, gen_out = _run(gen_cmd, timeout=30)
        checks.append(("generate_update_manifest", gen_code, gen_out))

        if download_url or resolve_github_repository():
            prep_cmd = [sys.executable, "scripts/release/prepare_release_manifest.py"]
            if download_url:
                prep_cmd.extend(["--download-url", download_url])
            else:
                prep_cmd.append("--github-release")
            if release_tag:
                prep_cmd.extend(["--tag", release_tag])
            prep_code, prep_out = _run(prep_cmd, timeout=30)
            checks.append(("prepare_release_manifest", prep_code, prep_out))
        elif strict:
            checks.append(
                (
                    "prepare_release_manifest",
                    1,
                    "FAIL set STT_AIO_UPDATE_DOWNLOAD_URL, GITHUB_REPOSITORY, or git origin",
                )
            )
        else:
            checks.append(("prepare_release_manifest", 0, "skip: no release URL env"))

        remote_manifest_url = os.environ.get("STT_AIO_MANIFEST_URL", "").strip()
        if remote_manifest_url:
            rm_cmd = [sys.executable, "scripts/release/verify_remote_manifest.py", "--url", remote_manifest_url]
            if release_tag:
                rm_cmd.extend(["--expected-version", release_tag.lstrip("vV")])
            rm_code, rm_out = _run(rm_cmd, timeout=30)
            checks.append(("verify_remote_manifest", rm_code, rm_out if rm_code else "pass"))
        elif strict and os.environ.get("STT_AIO_REQUIRE_REMOTE_MANIFEST"):
            checks.append(("verify_remote_manifest", 1, "FAIL set STT_AIO_MANIFEST_URL"))
        else:
            checks.append(("verify_remote_manifest", 0, "skip: no STT_AIO_MANIFEST_URL"))

        if gen_code == 0 and update_manifest.is_file():
            sys.path.insert(0, str(ROOT / "build"))
            try:
                from generate_update_manifest import verify_update_manifest  # noqa: WPS433
            finally:
                sys.path.pop(0)
            allow_ph = not strict and not download_url
            failures = verify_update_manifest(update_manifest, allow_placeholder=allow_ph)
            v_code = 0 if not failures else 1
            v_out = "pass" if not failures else "\n".join(failures)
            checks.append(("verify_update_manifest", v_code, v_out))
        elif strict:
            checks.append(("verify_update_manifest", 1, "FAIL update-manifest.json missing"))

        setup_exe = list((ROOT / "dist" / "installer").glob("STT-AIO-Setup-*.exe"))
        if setup_exe:
            i_code, i_out = _run_powershell("installer_smoke.ps1", timeout=900)
            checks.append(("installer_smoke", i_code, i_out))
        elif strict:
            checks.append(("installer_smoke", 1, "FAIL installer exe missing"))
        else:
            checks.append(("installer_smoke", 0, "skip: installer exe not built"))
    elif strict:
        checks.append(("verify_installer", 1, "FAIL build-manifest.json missing"))
        checks.append(("verify_release_tag", 1, "FAIL build-manifest.json missing"))
        checks.append(("generate_update_manifest", 1, "FAIL build-manifest.json missing"))
        checks.append(("verify_update_manifest", 1, "FAIL build-manifest.json missing"))
        checks.append(("prepare_release_manifest", 1, "FAIL build-manifest.json missing"))
        if run_build or strict:
            checks.append(("installer_smoke", 1, "FAIL build-manifest.json missing"))
    else:
        checks.append(("verify_installer", 0, "skip: build-manifest.json not built"))
        checks.append(("verify_release_tag", 0, "skip: build-manifest.json not built"))
        checks.append(("generate_update_manifest", 0, "skip: build-manifest.json not built"))
        checks.append(("verify_update_manifest", 0, "skip: build-manifest.json not built"))
        checks.append(("prepare_release_manifest", 0, "skip: build-manifest.json not built"))
        checks.append(("installer_smoke", 0, "skip: build-manifest.json not built"))
        if not dist.is_dir() or code != 0:
            checks.append(("bundle_smoke", 0, "skip: verify_bundle not passed"))

    code, out = _run([py, "scripts/bench/record_nfr_results.py"], timeout=300)
    checks.append(("record_nfr_results", code, out))

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import scripts.smoke.verify_ci_workflow as ci_mod

    wf_failures = ci_mod.verify_workflow_file() + ci_mod.verify_release_workflow_file()
    wf_code = 0 if not wf_failures else 1
    wf_out = "pass" if not wf_failures else "\n".join(wf_failures)
    checks.append(("ci_workflow_definition", wf_code, wf_out))

    gh_status, gh_detail = ci_mod.verify_github_run_status()
    gh_code = 0 if gh_status in {"pass", "skip", "pending"} else 1
    checks.append(("ci_github_run", gh_code, f"{gh_status}: {gh_detail}"))

    rel_status, rel_detail = ci_mod.verify_release_github_run_status()
    rel_code = 0 if rel_status in {"pass", "skip", "pending"} else 1
    checks.append(("ci_release_github_run", rel_code, f"{rel_status}: {rel_detail}"))

    nfr_code, nfr_out = _evaluate_nfr_gate()
    checks.append(("NFR packaged gate", nfr_code, nfr_out))

    rows = []
    max_exit = 0
    for name, exit_code, detail in checks:
        max_exit = max(max_exit, exit_code)
        if name in {"ci_github_run", "ci_release_github_run"}:
            prefix = detail.split(":", 1)[0]
            if prefix == "pass":
                status = "pass"
            elif prefix == "skip":
                status = f"skip: {detail.split(':', 1)[1].strip()}" if ":" in detail else "skip"
                exit_code = 0
            elif prefix == "pending":
                status = "pending"
                exit_code = 0
            else:
                status = f"fail({exit_code})"
        elif name in {"prepare_release_manifest", "verify_remote_manifest", "dist_freshness"}:
            if detail.startswith("skip:") or detail.startswith("warn:"):
                status = detail
                exit_code = 0
            elif detail.startswith("FAIL"):
                status = f"fail({exit_code})"
            else:
                status = "pass" if exit_code == 0 else f"fail({exit_code})"
        else:
            status = "pass" if exit_code == 0 else f"fail({exit_code})"
        rows.append(f"| {name} | {today} | {env} | {status} |")

    details = "\n\n".join(
        f"### {name}\n\n```\n{out[-4000:]}\n```" for name, _, out in checks
    )

    body = f"""# Release Checklist — 자동 검증 결과

자동 기록: `{Path(__file__).name}` ({today})

> 수동 항목(설치·실기기·매니페스트 게시)은 `docs/release_checklist.md` 참고.
> 릴리스 모드: `STT_AIO_RELEASE_BUILD=1 python scripts/smoke/release_checklist_smoke.py`
> 엄격 모드: `STT_AIO_RELEASE_STRICT=1` (dist/manifest 없으면 fail)
> 매니페스트 URL: `STT_AIO_UPDATE_DOWNLOAD_URL=https://…/Setup.exe`
> 릴리스 태그: `STT_AIO_RELEASE_TAG=v0.2.0` (미설정 시 manifest version에서 추론)
> CI green 필수: `STT_AIO_CI_REQUIRE_GREEN=1` (gh CLI 필요)

| 항목 | 날짜 | 환경 | 결과 |
|------|------|------|------|
{chr(10).join(rows)}
| Cloudflare Tunnel CLI | {today} | {env} | {tunnel_status} |

{details}

체크리스트: `docs/release_checklist.md`
"""
    RESULTS.write_text(body, encoding="utf-8")
    print(f"wrote {RESULTS}")

    sync_code, sync_out = _run([py, "scripts/smoke/sync_release_checklist.py"], timeout=30)
    if sync_code != 0:
        print(sync_out, file=sys.stderr)
    return max(max_exit, sync_code)


if __name__ == "__main__":
    raise SystemExit(main())
