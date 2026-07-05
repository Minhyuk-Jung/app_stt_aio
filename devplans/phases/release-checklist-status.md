# Release Checklist — 자동 매핑 상태

생성: `sync_release_checklist.py` (2026-07-05)

원본: `release_checklist.md` · 실측: `release-checklist-results.md`

| # | 체크리스트 항목 | 자동/수동 | 상태 |
|---|----------------|-----------|------|
| 1 | 자동 검증 | 자동 | ☑ auto-pass |
| 2 | 자동 검증 | 자동 | ☑ auto-pass |
| 3 | 자동 검증 | 자동 | ☑ auto-pass |
| 4 | 자동 검증 | 자동 | fail |
| 4b | 자동 검증 | 자동 | fail |
| 5 | 자동 검증 | 자동 | ☑ auto-pass |
| 6 | 자동 검증 | 자동 | ☑ auto-pass |
| 7 | 자동 검증 | 자동 | ☑ auto-pass |
| 8 | 자동 검증 | 자동 | ☑ auto-pass |
| 9 | 자동 검증 | 자동 | ☑ auto-pass |
| 10 | 자동 검증 | 자동 | ☑ auto-pass |
| 5b | GitHub Actions green | 자동/수동 | ◐ CI green 미확인 (gh 없음 또는 run 없음) |
| 11 | prepare_release_manifest (#11) | 자동/수동 | ☑ auto-pass |
| 12 | (수동) | 수동 | ◐ auto-proxy (수동 업데이트 확인 UI 동작; 설치본 수동 권장) |
| 13 | (수동) | 수동 | ◐ auto-proxy (다운로드·검증·설치 실행 흐름 (UI); 설치본 수동 권장) |

## 수동 잔여

- 모바일 실기기 E2E (`docs/p4_mobile_e2e.md`)
- cloudflared 실환경 (`tunnel_live_smoke.py`)
- C22 매니페스트 호스팅 URL 확정 (`DECISIONS.md`)
- #11 잔여: Release 게시 후 앱 `update.manifest_url` 설정 (`docs/release_guide.md`)
