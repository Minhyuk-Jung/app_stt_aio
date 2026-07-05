"""Tests for verify_ci_workflow.py."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_verify_workflow_file_passes_current_build_yml() -> None:
    import scripts.smoke.verify_ci_workflow as mod

    failures = mod.verify_workflow_file()
    assert failures == [], failures


def test_verify_workflow_file_detects_missing_fragment(tmp_path: Path, monkeypatch) -> None:
    import scripts.smoke.verify_ci_workflow as mod

    wf = tmp_path / "build.yml"
    wf.write_text("name: test\non: push\n", encoding="utf-8")
    monkeypatch.setattr(mod, "WORKFLOW", wf)
    failures = mod.verify_workflow_file()
    assert failures
    assert any("pytest" in f or "verify_ci" in f for f in failures)


def test_verify_release_workflow_file_passes() -> None:
    import scripts.smoke.verify_ci_workflow as mod

    assert mod.verify_release_workflow_file() == []


def test_verify_release_github_run_status_delegates(monkeypatch) -> None:
    import scripts.smoke.verify_ci_workflow as mod

    monkeypatch.setattr(mod, "_verify_github_workflow_run", lambda wf: ("skip", f"wf={wf}"))
    status, detail = mod.verify_release_github_run_status()
    assert status == "skip"
    assert detail == "wf=release.yml"


def test_verify_composite_action_passes() -> None:
    import scripts.smoke.verify_ci_workflow as mod

    assert mod.verify_composite_action() == []


def test_verify_workflow_requires_composite_reference() -> None:
    import scripts.smoke.verify_ci_workflow as mod

    failures = mod.verify_workflow_file()
    assert failures == []
    text = mod.WORKFLOW.read_text(encoding="utf-8")
    assert mod.COMPOSITE_REFERENCE in text
    assert "verify_ci_workflow.py" in text
    assert "--ignore=tests/ui" in mod.COMPOSITE_ACTION.read_text(encoding="utf-8")
