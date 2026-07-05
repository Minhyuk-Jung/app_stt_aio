# P4 Handoff — 원격 위성 (갱신 2026-07-05)

## P4 목표 (README §8)

모바일/웹을 **녹음 전용 위성**으로 연결 — PWA 녹음 → 터널(QR/PIN) → 허브 파이프라인 투입.

## 완료 요약

| 항목 | 상태 | 비고 |
|------|------|------|
| FastAPI 게이트웨이 + PWA | ● | `remote/gateway/app.py`, `pwa/index.html` |
| PIN/토큰 페어링 | ● | `pairing.py`, TTL·lockout·C19 secret |
| WebM/WAV ingest | ● | `ingest.py`, ffmpeg WebM |
| SessionManager 연동 | ● | `submit_remote()` → 실제 stage1 파이프라인 |
| QR 표시 (설정 UI) | ● | `app/ui/qr_util.py` |
| Cloudflare Tunnel | ◐ | `tunnel.py` 재시도, CLI 미설치 시 skip |
| 자동 E2E (ASGI) | ● | pair → upload → session + **artifact DB** (mock 제거) |
| 업로드 보안 | ● | 401/413/400/429, 토큰·녹음 길이·페어링 lockout |
| PWA 번들 (C16) | ● | `pyinstaller.spec` datas + `resolve_pwa_dir()` |
| PWA UX | ● | HTTPS 고지, mimeType 폴백, 401 재페어링, 업로드 재시도 |
| 모바일 실기기 E2E | ◐ | **수동** — `docs/p4_mobile_e2e.md` |

## 갭 보완 (2026-07-05)

| 갭 | 조치 |
|----|------|
| PyInstaller PWA 미번들 | `build/pyinstaller.spec`에 `remote/gateway/pwa` datas 추가, `verify_bundle.py` 검증 |
| artifact E2E mock | `test_gateway_session.py` — `run_stage1`+`inject_stage_text` 실경로 검증, 동시 업로드 테스트 |
| 페어링 brute-force | `PairingManager` lockout (5회/60초), C19 `remote.pairing_secret` 저장 |
| PWA 모바일 UX | mimeType 폴백, 401 토큰 삭제, 업로드 3회 재시도, 429 메시지 |
| Tunnel 불안정 | `start(max_attempts=2)`, `tunnel_live_smoke.py` 실환경 스크립트 |
| 녹음 길이 상한 | `MAX_REMOTE_DURATION_MS=600_000` (10분) → 413 |

## 자동 검증 (2026-07-05)

```bash
python -m pytest tests/remote tests/build/test_packaging.py tests/services/test_remote_gateway_service.py -q
python -m pytest tests/ -q --ignore=tests/ui
python scripts/smoke/tunnel_check.py
python scripts/smoke/tunnel_live_smoke.py      # cloudflared 있을 때 /health 실측
python scripts/smoke/record_p4_results.py      # → devplans/phases/P4-results.md
```

### 테스트 목록

- `tests/remote/test_gateway_security.py` — 401/413/400/429 lockout, 녹음 길이 413
- `tests/remote/test_tunnel.py` — URL 파싱, 재시도, cloudflared 없음
- `tests/remote/test_pairing.py` — PIN TTL, lockout, C19 secret
- `tests/remote/test_app_pwa.py` — `resolve_pwa_dir()` frozen/dev 경로
- `tests/remote/test_gateway_session.py` — artifact DB 실경로, 동시 업로드
- `tests/build/test_packaging.py` — spec PWA datas, verify_bundle
- `tests/services/test_remote_gateway_service.py` — Tunnel 실패 시 로컬 URL 폴백

## P4 진입 조건 체크리스트

- [x] PIN/토큰 페어링 + PWA
- [x] WebM ingest (ffmpeg)
- [x] C14 원격 녹음 설정 탭 + 트레이 진입
- [x] QR 이미지 표시
- [x] gateway E2E (`test_gateway_e2e.py`)
- [x] SessionManager + artifact DB E2E (실경로 파이프라인)
- [x] 업로드 제한·인증·페어링 lockout 테스트
- [x] PyInstaller PWA 번들 + verify
- [ ] 모바일 브라우저 → 허브 artifact (**실기기 — 사용자**)
- [ ] Cloudflare Tunnel 실환경 (`cloudflared` 설치 후 `tunnel_live_smoke.py`)

## 미구현 (P5 이후)

- CI에 tunnel live smoke 필수화 (현재 optional)
- C22 3단계 코드사인 (미결정)

## PWA 청크 업로드 (2026-07-05)

- 서버: `/api/v1/transcribe/chunks/init`, `/chunk`
- PWA: 512KiB 이상 blob → 자동 청크 분할·재시도

## LAN 폴백 (2026-07-05 갱신)

- Tunnel **실패 시에만** `0.0.0.0` rebind (`remote.lan_fallback`)
- `/api/v1/access`에서 PIN 제거 (보안)
- 모바일 녹음은 **HTTPS(Tunnel) 필수** — LAN HTTP는 PC 테스트용

## P5로 넘길 정보

- 네트워크 실패: Tunnel 미설치 시 로컬 URL만 — 모바일 HTTPS 불가
- Tunnel 실패 시 `RemoteGatewayService`가 로컬 URL로 폴백 (경고 로그)
- 업로드 상한: 32 MiB, 녹음 길이 10분
- PIN TTL 10분, 토큰 TTL 24시간, 페어링 lockout 5회/60초

## 다음 우선순위

1. 모바일 실기기 E2E (사용자, `docs/p4_mobile_e2e.md`)
2. `cloudflared` 설치 후 `tunnel_live_smoke.py` 실행
3. P5 잔여 (C22 코드사인 3단계 — 미결정)

테스트 기준선: **458 passed** (2026-07-05, UI 제외, `record_p4_results.py` 참고).
