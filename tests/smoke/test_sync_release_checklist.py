"""Tests for sync_release_checklist.py."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sync_maps_auto_pass_from_results(tmp_path: Path, monkeypatch) -> None:
    results = tmp_path / "release-checklist-results.md"
    results.write_text(
        """| 항목 | 날짜 | 환경 | 결과 |
|------|------|------|------|
| pytest (UI 제외) | 2026-07-05 | x | pass |
| verify_bundle | 2026-07-05 | x | pass |
| bundle_smoke | 2026-07-05 | x | pass |
| build.py --portable | 2026-07-05 | x | pass |
| verify_update_manifest | 2026-07-05 | x | pass |
| ci_workflow_definition | 2026-07-05 | x | pass |
| ci_github_run | 2026-07-05 | x | skip: gh CLI not available |
""",
        encoding="utf-8",
    )
    out = tmp_path / "status.md"
    checklist = tmp_path / "release_checklist.md"
    checklist.write_text(
        "| # | 항목 | 확인 |\n|---|------|------|\n| 6 | pytest | ☐ |\n| 4b | update manifest | ☐ |\n",
        encoding="utf-8",
    )

    import scripts.smoke.sync_release_checklist as mod

    monkeypatch.setattr(mod, "RESULTS", results)
    monkeypatch.setattr(mod, "OUTPUT", out)
    monkeypatch.setattr(mod, "CHECKLIST", checklist)
    assert mod.main() == 0
    text = out.read_text(encoding="utf-8")
    assert "☑ auto-pass" in text
    assert "| 6 |" in text
    assert "| 4b |" in text
    assert "| 5 |" in text
    assert "☑" in checklist.read_text(encoding="utf-8")


def test_sync_flags_missing_build_when_dist_built(tmp_path: Path, monkeypatch) -> None:
    results = tmp_path / "release-checklist-results.md"
    results.write_text(
        """| 항목 | 날짜 | 환경 | 결과 |
|------|------|------|------|
| verify_bundle | 2026-07-05 | x | pass |
| bundle_smoke | 2026-07-05 | x | pass |
| dist_freshness | 2026-07-05 | x | pass |
| verify_installer | 2026-07-05 | x | pass |
| generate_update_manifest | 2026-07-05 | x | pass |
| verify_update_manifest | 2026-07-05 | x | pass |
| installer_smoke | 2026-07-05 | x | pass |
| ci_workflow_definition | 2026-07-05 | x | pass |
| pytest (UI 제외) | 2026-07-05 | x | pass |
| ko_wer 회귀 (non-integration) | 2026-07-05 | x | pass |
| record_nfr_results | 2026-07-05 | x | pass |
| NFR packaged gate | 2026-07-05 | x | pass |
""",
        encoding="utf-8",
    )
    out = tmp_path / "status.md"
    import scripts.smoke.sync_release_checklist as mod

    monkeypatch.setattr(mod, "RESULTS", results)
    monkeypatch.setattr(mod, "OUTPUT", out)
    monkeypatch.setattr(mod, "CHECKLIST", tmp_path / "missing.md")
    mod.main()
    text = out.read_text(encoding="utf-8")
    assert "build.py --portable" in text
    assert "◐" in text


def test_apply_checkmarks_reverts_when_not_auto_pass(tmp_path: Path) -> None:
    import scripts.smoke.sync_release_checklist as mod

    checklist = tmp_path / "checklist.md"
    checklist.write_text(
        "| # | 항목 | 확인 |\n|---|------|------|\n| 5b | CI | ☑ |\n",
        encoding="utf-8",
    )
    n = mod.apply_checkmarks_to_checklist(checklist, {"5b": "◐ pending"})
    assert n == 1
    assert "| 5b | CI | ☐ |" in checklist.read_text(encoding="utf-8")


def test_evaluate_prepare_considers_verify_release_tag() -> None:
    import scripts.smoke.sync_release_checklist as mod

    assert mod.evaluate_prepare_release_manifest(
        {"prepare_release_manifest": "pass", "verify_release_tag": "pass"}
    ) == "☑ auto-pass"
    assert mod.evaluate_prepare_release_manifest(
        {"prepare_release_manifest": "skip: no env", "verify_release_tag": "pass"}
    ).startswith("◐")
    assert mod.evaluate_prepare_release_manifest(
        {"prepare_release_manifest": "pass", "verify_release_tag": "fail(1)"}
    ) == "fail"
    assert mod.evaluate_prepare_release_manifest(
        {"verify_remote_manifest": "pass", "prepare_release_manifest": "skip: x"}
    ) == "☑ auto-pass"


def test_evaluate_ui_proxy_passes_with_automation() -> None:
    import scripts.smoke.sync_release_checklist as mod

    state = mod.evaluate_ui_proxy({"update_ui_automation": "pass"}, "업데이트 UI")
    assert state.startswith("◐ auto-proxy")


def test_apply_checkmarks_only_auto_pass(tmp_path: Path) -> None:
    import scripts.smoke.sync_release_checklist as mod

    checklist = tmp_path / "checklist.md"
    checklist.write_text(
        "| # | 항목 | 확인 |\n|---|------|------|\n| 1 | build | ☐ |\n| 5 | CI | ☐ |\n",
        encoding="utf-8",
    )
    n = mod.apply_checkmarks_to_checklist(checklist, {"1": "☑ auto-pass", "5": "☐ manual"})
    assert n == 1
    text = checklist.read_text(encoding="utf-8")
    assert "| 1 | build | ☑ |" in text
    assert "| 5 | CI | ☐ |" in text
