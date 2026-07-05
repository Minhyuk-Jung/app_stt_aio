# P5 Closure — 안정화/업데이트 완료 보고

> `README.md` §8.1 P5 DoD · §8.2 Phase 인수인계 기준

**완료일**: 2026-07-05  
**테스트 기준선**: 483+ passed (UI 제외)

---

## 1. P5 목표 달성 요약

| 영역 | 상태 | 산출물 |
|------|------|--------|
| NFR 벤치 | ● | `P5-nfr-results.md` |
| C22 업데이트 1~2단계 | ● | `core/updater/`, `docs/update_policy.md` |
| C22 3단계 코드사인 | ○ | 미결정 (`DECISIONS.md` §3) |
| C15 LAN·청크·진단 | ● | `P5-handoff.md` |
| C16 패키징 검증 | ● | verify_bundle·installer_smoke 로컬 pass (2026-07-05) |
| C16 PyInstaller 가드 | ● | `build/build_env.py` — pathlib backport·venv Python |
| 릴리스 체크리스트 | ◐ | 자동: #1~#10·#5 / 수동·◐: #5b CI green, #11~#13 |
| 알려진 이슈 | ● | `docs/known_issues.md` |

---

## 2. 기술 결정 기록

| 결정 | 근거 |
|------|------|
| SQLite `Database`에 `RLock` | 워커·HTTP 스레드 동시 DB 접근 시 savepoint 깨짐 방지 |
| Tunnel 실패 시에만 LAN rebind | C15 §7 보안 기본값 `127.0.0.1` 유지 |
| 청크 `is_final` 연속 index 검증 | 조립 누락·순서 오류 조기 400 |
| 업데이트 3단계 보류 | 코드사인 전 자동 설치 비활성 (`C22-updater.md`) |

---

## 3. 측정값

- pytest (UI 제외): **479 passed**
- ko_wer non-integration: 4 passed
- NFR: `scripts/bench/record_nfr_results.py` → `P5-nfr-results.md`
- verify_bundle: **pass** (`.venv` + `build.py --portable`, 2026-07-05)

---

## 4. API 계약 (운영·후속 참고)

| 계약 | 위치 |
|------|------|
| 청크 업로드 | `POST /api/v1/transcribe/chunks/init`, `POST /api/v1/transcribe/chunk` |
| 페어링 | `POST /api/v1/pair`, Bearer 토큰 |
| 접속 정보 | `GET /api/v1/access` (PIN 미노출) |
| 업데이트 매니페스트 | `docs/update_policy.md`, `build/sample-update-manifest.json` |
| 빌드 매니페스트 | `dist/installer/build-manifest.json` |

---

## 5. 실패 사례·회피책

| 사례 | 회피책 |
|------|--------|
| cloudflared 미설치 | `tunnel_check` skip, Tunnel UI 비활성 |
| SmartScreen (미서명) | `build/SMARTSCREEN.txt` 안내 |
| 모바일 실기기 E2E | `docs/p4_mobile_e2e.md` 수동 |
| stale `dist/` | `STT_AIO_RELEASE_BUILD=1` 로 스모크 재실행 |
| Anaconda pathlib backport | `.venv` Python 또는 `build_env.py` 가드 |
| placeholder update URL | `STT_AIO_UPDATE_DOWNLOAD_URL` 또는 strict 시 fail |

---

## 6. 수동 잔여 (릴리스 시)

- [ ] `python build/build.py --portable` + `--installer --require-installer`
- [ ] `docs/release_checklist.md` 설치·실기기·매니페스트 게시
- [ ] GitHub Releases에 `build-manifest.json` checksum 반영한 update manifest 게시
- [ ] (선택) 코드사인 확정 시 C22 3단계

---

## 7. 자동 검증 명령

```bash
python -m pytest tests/ -q --ignore=tests/ui
python scripts/smoke/record_p5_results.py
python scripts/smoke/release_checklist_smoke.py
# 릴리스 (빌드+검증): .venv 권장
# STT_AIO_RELEASE_BUILD=1 python scripts/smoke/release_checklist_smoke.py
# 검증만: STT_AIO_RELEASE_STRICT=1 python scripts/smoke/release_checklist_smoke.py
# 매니페스트 URL: STT_AIO_UPDATE_DOWNLOAD_URL=https://…/Setup.exe
```

---

## 8. 로드맵 이후

README §8 기준 **P0~P5가 마스터 로드맵 전체**입니다. 후속 작업은 **`P6-commercialization.md`** (CI·릴리스·매니페스트 게시)에서 관리합니다. 코드사인·매니페스트 호스팅 확정은 `DECISIONS.md` 회의 안건입니다.

관련: `P5-handoff.md`, `release-checklist-results.md`, `P5-stabilization-results.md`
