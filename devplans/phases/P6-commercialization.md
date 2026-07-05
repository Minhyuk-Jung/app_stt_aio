# P6 — 상용화/릴리스 운영 (post-P5)

> `README.md` §8 로드맵 P0~P5 완료 후 후속 단계. `P5-closure.md` §8, `DECISIONS.md` 회의 안건 기반.

**시작일**: 2026-07-05  
**선행 조건**: P5 DoD 자동 항목 pass (`release-checklist-status.md`)

---

## 1. 목표

개인용 알파에서 **반복 가능한 릴리스 파이프라인**과 **업데이트 채널**을 확립한다. 코드사인·실기기 E2E는 정책 확정 후 단계적으로 포함한다.

---

## 2. 범위

### In scope (P6)

| # | 항목 | 산출물 |
|---|------|--------|
| 1 | CI `build.yml` 정합·로컬 검증 | `verify_ci_workflow.py`, workflow 수정 |
| 2 | 릴리스 스모크 완전 커버 | installer_smoke, CI 단계 매핑 |
| 3 | update-manifest 게시 준비 | CI artifact + `STT_AIO_UPDATE_DOWNLOAD_URL` 문서 |
| 4 | C22 UI 흐름 자동 검증 | `update_check_logic` 단위 테스트 (#12/#13) |
| 5 | 수동 잔여 가이드 | `docs/p4_mobile_e2e.md`, `docs/release_checklist.md` |

### Out of scope (DECISIONS 회의)

- C22 3단계 자동 업데이트 (코드사인 후)
- GPU 번들·기본 모델 크기 변경
- macOS/Linux 이식 (`README` §15 백로그)

---

## 3. 개발 절차 (권장 순서)

```
1. CI workflow 정합 (build.yml ↔ release_checklist)
   ↓
2. verify_ci_workflow + release_checklist_smoke 연동
   ↓
3. installer_smoke 기본 스모크 포함
   ↓
4. C22 UI 로직 테스트 (#12/#13)
   ↓
5. GitHub Releases 매니페스트 게시 (#11) — 호스팅 URL 확정 후
   ↓
6. 모바일 실기기 E2E / tunnel_live (수동)
```

---

## 4. 완료 기준 (DoD)

- [x] `verify_ci_workflow.py` pass (build.yml 필수 단계 포함)
- [x] `release_checklist_smoke.py` — checklist #3~#10, #5 (dist 있을 때; **#1/#2는 BUILD 시 pass**)
- [x] checklist #3 `installer_smoke` (dist/installer 있을 때)
- [x] C22 통합 테스트 (`test_update_flow_integration.py`)
- [x] `prepare_release_manifest.py` (#11 준비)
- [x] `verify_release_tag.py` — tag ↔ build-manifest 정합
- [x] `verify_remote_manifest.py` — 게시 후 원격 manifest 검증
- [x] `pre_release_gate.py` — 릴리스 전 통합 게이트
- [x] 트레이·설정 업데이트 진입점 테스트 (`test_update_entry_points.py`)
- [x] `.github/actions/windows-build-smoke` — build/release workflow 공통화
- [x] `post_release_checklist.py` — Release 게시 후 검증
- [x] `verify_dist_freshness.py` — stale dist 경고 (#1/#2)
- [x] `pre_release_gate.py --quick` — CI·태그만 빠른 검증
- [ ] CI `build.yml` push/PR green (#5b, GitHub Actions 실측)
- [ ] checklist #11 실제 Release 게시 후 `update.manifest_url` 설정
- [ ] checklist #12~13 UI 수동 확인

관련 가이드: `docs/release_guide.md`

---

## 5. 자동 검증 명령

```bash
python scripts/smoke/verify_ci_workflow.py
python scripts/smoke/release_checklist_smoke.py
# 전체 빌드 포함:
STT_AIO_RELEASE_BUILD=1 python scripts/smoke/release_checklist_smoke.py
# 릴리스 엄격:
STT_AIO_RELEASE_STRICT=1 STT_AIO_UPDATE_DOWNLOAD_URL=https://… python scripts/smoke/release_checklist_smoke.py
```

---

## 6. 인수인계

완료 시 `P6-closure.md` 작성. 미결정은 `DECISIONS.md`에 기록.

관련: `P5-closure.md`, `C22-updater.md`, `C16-packaging.md`, `docs/update_policy.md`
