# P5 Handoff — 안정화/업데이트 (갱신 2026-07-05, 갭 보완)

## P5 목표 (README §8)

제품 운영 품질 향상 — 성능 튜닝, 반자동 업데이트, 장기 회귀, 장애 진단.

## 갭 보완 (2026-07-05 3차)

| 갭 | 조치 |
|----|------|
| PyInstaller + Anaconda pathlib | `build/build_env.py` 가드, venv Python 우선 |
| update-manifest placeholder | `verify_update_manifest`, strict 시 fail |
| 체크리스트 동기화 | `sync_release_checklist.py` → `release-checklist-status.md` + `docs/release_checklist.md` ☑ |

## 갭 보완 (2026-07-05 2차)

| 갭 | 조치 |
|----|------|
| LAN 폴백 정책 (C15 §7) | Tunnel **실패 시에만** `rebind(0.0.0.0)`; 기본 `127.0.0.1` |
| `/api/v1/access` PIN 노출 | PIN 제거, `status`+`pwa`만 반환 + 테스트 |
| 청크 업로드 (C15 §3) | `/transcribe/chunks/init`, `/transcribe/chunk` + `ChunkAssembler` |
| uvicorn ready | `/health` 폴링 후 접속 정보 반환 |
| Tunnel 끊김 | `tunnel_is_connected()` / diagnostics `tunnel_connected` |
| UI/QR | HTTPS(public) URL만 QR; LAN은 텍스트 안내만 |
| 진단 스냅샷 | bind_host, port, tunnel_error, mobile_recording_available |
| 온보딩 진단 | `SettingsController`에 gateway 연결 |
| CI | `tunnel_live_smoke.py` optional step |
| 문서 | `p4_mobile_e2e.md` 방화벽·LAN 한계, `known_issues` KI-008/009 |

## 완료 요약

| 항목 | 상태 | 비고 |
|------|------|------|
| NFR 벤치 | ● | `P5-nfr-results.md` |
| C22 1~2단계 | ● | 수동 확인·다운로드·검증 |
| C15 LAN 폴백 | ● | 조건부 rebind (Tunnel 실패 시) |
| C15 청크 API + PWA UX | ◐ | FormData 재시도·upload_id 유지 재개; 실기기 E2E 잔여 |
| C20 진단 | ● | remote_gateway 확장 필드 |
| C22 3단계 | ○ | 코드사인 미결정 |
| 모바일 실기기 E2E | ◐ | 수동 `docs/p4_mobile_e2e.md` |

## 자동 검증

```bash
python -m pytest tests/ -q --ignore=tests/ui
python scripts/smoke/record_p5_results.py
python scripts/smoke/tunnel_live_smoke.py   # cloudflared 있을 때
```

## P4 잔여

- [ ] 모바일 실기기 E2E
- [ ] cloudflared 실환경 (`tunnel_live_smoke.py`)
- [x] PWA 청크 업로드 UX (512KiB 이상 자동 청크)

## P5 DoD

- [x] LAN/보안/청크 갭 보완
- [x] 진단·CI·문서
- [x] `release_checklist_smoke.py` + `sync_release_checklist.py` (strict·verify_update_manifest)
- [x] `build/build_env.py` PyInstaller 가드
- [x] SQLite 멀티스레드 DB 안정화 (`Database._conn_lock`)
- [x] `P5-closure.md` 인수인계 문서
- [ ] `release_checklist.md` 수동 항목 (#5b CI green, #11~13 매니페스트·UI)
- [ ] C22 3단계 (코드사인)

```bash
python scripts/smoke/release_checklist_smoke.py
# 패키지 검증 포함:
# STT_AIO_RELEASE_BUILD=1 python scripts/smoke/release_checklist_smoke.py
# 엄격 (placeholder URL 불가):
# STT_AIO_RELEASE_STRICT=1 STT_AIO_UPDATE_DOWNLOAD_URL=https://… python scripts/smoke/release_checklist_smoke.py
```

- 테스트 기준선: **479 passed** (2026-07-05, UI 제외).

**Phase 종료**: `devplans/phases/P5-closure.md`  
**다음 단계**: `devplans/phases/P6-commercialization.md`
