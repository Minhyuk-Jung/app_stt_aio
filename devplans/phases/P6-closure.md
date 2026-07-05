# P6 Closure — 상용화/릴리스 운영 (완료 보고)

> `P6-commercialization.md` DoD · `P5-closure.md` 후속

**기준일**: 2026-07-05  
**테스트 기준선**: **525 passed** (UI 제외)

---

## 1. P6 목표 달성 요약

| 영역 | 상태 | 산출물 |
|------|------|--------|
| CI workflow composite | ● | `.github/actions/windows-build-smoke` |
| 릴리스 태그·manifest 검증 | ● | `verify_release_tag`, `verify_remote_manifest` |
| 릴리스 전/후 게이트 | ● | `pre_release_gate.py`, `post_release_checklist.py` |
| dist freshness (#1/#2) | ● | `verify_dist_freshness.py`, `build-stamp.json` |
| #12/#13 UI auto-proxy | ◐ | `update_ui_automation` pytest |
| 릴리스 체크리스트 자동 | ◐ | #3~#11 pass; #1/#2는 `STT_AIO_RELEASE_BUILD=1` |
| CI green 실측 (#5b) | ○ | push/tag + gh CLI |
| 설치본 UI (#12~#13) | ○ | auto-proxy 외 수동 권장 |

---

## 2. 기술 결정 (P6 잠정)

| 결정 | 근거 |
|------|------|
| 매니페스트 호스팅 GitHub Releases | `DECISIONS.md` P6 잠정 |
| 태그 `v{semver}` ↔ manifest version 일치 | `verify_release_tag.py` |
| workflow 공통화 composite action | build/release.yml 유지보수 |
| dist stale 경고 | `pyproject.toml` mtime vs exe |

---

## 3. 측정값 (2026-07-05)

- pytest (UI 제외): **525 passed**
- `verify_ci_workflow.py`: composite + workflows OK
- `release_checklist_smoke.py`: exit 0 (dist freshness warn 가능)

---

## 4. 수동 잔여 (릴리스 시)

- [ ] `python scripts/smoke/pre_release_gate.py --tag vX.Y.Z --build`
- [ ] `git push` + `STT_AIO_CI_REQUIRE_GREEN=1`
- [ ] `python scripts/release/post_release_checklist.py --tag vX.Y.Z`
- [ ] 설치본 업데이트 UI (#12~#13)
- [ ] C22 3단계 코드사인 (`DECISIONS.md`)

---

## 5. 자동 검증 명령

```bash
python scripts/smoke/pre_release_gate.py --tag v0.1.0 --quick
python scripts/smoke/release_checklist_smoke.py
STT_AIO_RELEASE_BUILD=1 python scripts/smoke/pre_release_gate.py --tag v0.1.0 --build
python scripts/release/post_release_checklist.py --tag v0.1.0 --manifest-url https://…
pytest tests/ -q --ignore=tests/ui
```

---

## 6. 관련 문서

- `docs/release_guide.md`
- `docs/update_policy.md`
- `devplans/phases/release-checklist-results.md`
