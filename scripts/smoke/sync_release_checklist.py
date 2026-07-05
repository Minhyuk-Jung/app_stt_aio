"""Map release-checklist-results.md to docs/release_checklist.md items (P5/P6 DoD)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "devplans" / "phases" / "release-checklist-results.md"
OUTPUT = ROOT / "devplans" / "phases" / "release-checklist-status.md"
CHECKLIST = ROOT / "docs" / "release_checklist.md"

MANUAL_ITEMS: dict[str, str] = {
    "12": "수동 업데이트 확인 UI 동작",
    "13": "다운로드·검증·설치 실행 흐름 (UI)",
}

UI_PROXY_KEY = "update_ui_automation"


@dataclass(frozen=True)
class AutoRule:
    """Checklist id -> smoke keys. `build_keys` required when dist is already built."""

    item_id: str
    required: tuple[str, ...]
    build_keys: tuple[str, ...] = ()


AUTO_RULES: tuple[AutoRule, ...] = (
    AutoRule("1", ("verify_bundle", "bundle_smoke", "dist_freshness"), ("build.py --portable",)),
    AutoRule("2", ("verify_installer",), ("build.py --installer",)),
    AutoRule("3", ("installer_smoke",)),
    AutoRule("4", ("verify_installer", "generate_update_manifest")),
    AutoRule("4b", ("verify_update_manifest",)),
    AutoRule("5", ("ci_workflow_definition",)),
    AutoRule("6", ("pytest (UI 제외)",)),
    AutoRule("7", ("ko_wer 회귀 (non-integration)",)),
    AutoRule("8", ("record_nfr_results", "NFR packaged gate")),
    AutoRule("9", ("record_nfr_results",)),
    AutoRule("10", ("NFR packaged gate",)),
)


def _parse_results_table(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("| 항목") or line.startswith("|------"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 4:
            rows[parts[0]] = parts[3]
    return rows


def _is_pass(status: str) -> bool:
    return status == "pass" or status == "skip"


def evaluate_rule(rule: AutoRule, smoke: dict[str, str], *, dist_built: bool) -> str:
    statuses = [smoke.get(name, "missing") for name in rule.required]
    for name, status in zip(rule.required, statuses):
        if status.startswith("warn:"):
            return f"◐ {name}: {status.removeprefix('warn:').strip()}"
    if any(s.startswith("fail") for s in statuses):
        return "fail"
    if any(s == "missing" for s in statuses):
        return "◐ skip/missing"
    if not all(_is_pass(s) for s in statuses):
        return "◐ " + ", ".join(f"{n}={s}" for n, s in zip(rule.required, statuses))

    for build_key in rule.build_keys:
        bs = smoke.get(build_key, "missing")
        if bs.startswith("fail"):
            return "fail"
        if bs == "missing":
            if dist_built:
                return f"◐ {build_key} not run (STT_AIO_RELEASE_BUILD=1)"
            continue
        if not _is_pass(bs):
            return "◐ " + f"{build_key}={bs}"

    return "☑ auto-pass"


def evaluate_prepare_release_manifest(smoke: dict[str, str]) -> str:
    raw = smoke.get("prepare_release_manifest", "missing")
    tag_raw = smoke.get("verify_release_tag", "missing")
    remote_raw = smoke.get("verify_remote_manifest", "missing")
    if raw.startswith("fail") or tag_raw.startswith("fail") or remote_raw.startswith("fail"):
        return "fail"
    if remote_raw == "pass":
        return "☑ auto-pass"
    if raw == "pass" and tag_raw == "pass":
        return "☑ auto-pass"
    if raw == "pass" and tag_raw.startswith("skip"):
        return "◐ manifest 준비됨, 태그 검증 스킵"
    if raw == "pass":
        return "☑ auto-pass"
    if raw.startswith("skip"):
        if tag_raw == "pass":
            return "◐ manifest URL env 없음 (태그·installer는 OK)"
        return "◐ manifest 준비 스킵 (STT_AIO_UPDATE_DOWNLOAD_URL 또는 GITHUB_REPOSITORY)"
    if raw.startswith("fail"):
        return "fail"
    if raw == "missing":
        return "◐ skip/missing"
    return f"◐ {raw}"


def evaluate_ui_proxy(smoke: dict[str, str], note: str) -> str:
    raw = smoke.get(UI_PROXY_KEY, "missing")
    if raw == "pass":
        return f"◐ auto-proxy ({note}; 설치본 수동 권장)"
    if raw.startswith("fail"):
        return "fail"
    if raw == "missing":
        return f"☐ {note}"
    return f"☐ {note}"


def evaluate_ci_github_run(smoke: dict[str, str]) -> str:
    raw = smoke.get("ci_github_run", "missing")
    if raw == "pass":
        return "☑ auto-pass"
    if raw.startswith("skip"):
        return "◐ CI green 미확인 (gh 없음 또는 run 없음)"
    if raw.startswith("pending"):
        return "◐ CI run in progress"
    if raw.startswith("fail"):
        return "fail"
    if raw == "missing":
        return "◐ skip/missing"
    return f"◐ {raw}"


def apply_checkmarks_to_checklist(checklist_path: Path, states: dict[str, str]) -> int:
    """Mark auto-pass rows in docs/release_checklist.md. Returns number of lines updated."""
    text = checklist_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    updated = 0
    new_lines: list[str] = []
    for line in lines:
        match = re.match(r"^\| (\d+b?)\s+\|(.+)\|\s*([☐☑])", line)
        if not match:
            new_lines.append(line)
            continue
        item_id, _middle, mark = match.groups()
        state = states.get(item_id)
        if state == "☑ auto-pass" and mark == "☐":
            new_lines.append(re.sub(r"(\|\s*)☐", r"\1☑", line, count=1))
            updated += 1
        elif state != "☑ auto-pass" and mark == "☑":
            new_lines.append(re.sub(r"(\|\s*)☑", r"\1☐", line, count=1))
            updated += 1
        else:
            new_lines.append(line)
    if updated:
        checklist_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return updated


def main() -> int:
    today = date.today().isoformat()
    if not RESULTS.is_file():
        print(f"missing {RESULTS} — run release_checklist_smoke.py first", flush=True)
        return 1

    smoke = _parse_results_table(RESULTS.read_text(encoding="utf-8"))
    dist_built = smoke.get("verify_bundle") == "pass"
    states: dict[str, str] = {}

    lines = [
        "# Release Checklist — 자동 매핑 상태",
        "",
        f"생성: `sync_release_checklist.py` ({today})",
        "",
        f"원본: `{CHECKLIST.name}` · 실측: `{RESULTS.name}`",
        "",
        "| # | 체크리스트 항목 | 자동/수동 | 상태 |",
        "|---|----------------|-----------|------|",
    ]

    fail = 0
    for rule in AUTO_RULES:
        state = evaluate_rule(rule, smoke, dist_built=dist_built)
        states[rule.item_id] = state
        if state == "fail":
            fail += 1
        lines.append(f"| {rule.item_id} | 자동 검증 | 자동 | {state} |")

    gh_state = evaluate_ci_github_run(smoke)
    states["5b"] = gh_state
    if gh_state == "fail":
        fail += 1
    lines.append(f"| 5b | GitHub Actions green | 자동/수동 | {gh_state} |")

    prep_state = evaluate_prepare_release_manifest(smoke)
    states["11"] = prep_state
    if prep_state == "fail":
        fail += 1
    lines.append(f"| 11 | prepare_release_manifest (#11) | 자동/수동 | {prep_state} |")

    for item_id, note in MANUAL_ITEMS.items():
        ui_state = evaluate_ui_proxy(smoke, note)
        states[item_id] = ui_state
        if ui_state == "fail":
            fail += 1
        lines.append(f"| {item_id} | (수동) | 수동 | {ui_state} |")

    lines.extend(
        [
            "",
            "## 수동 잔여",
            "",
            "- 모바일 실기기 E2E (`docs/p4_mobile_e2e.md`)",
            "- cloudflared 실환경 (`tunnel_live_smoke.py`)",
            "- C22 매니페스트 호스팅 URL 확정 (`DECISIONS.md`)",
            "- #11 잔여: Release 게시 후 앱 `update.manifest_url` 설정 (`docs/release_guide.md`)",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUTPUT}")

    if CHECKLIST.is_file():
        n = apply_checkmarks_to_checklist(CHECKLIST, states)
        if n:
            print(f"updated {n} row(s) in {CHECKLIST}")

    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
