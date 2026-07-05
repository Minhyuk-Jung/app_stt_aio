# STT-AIO 알려진 이슈

> P5 DoD 필수 산출물 (`README.md` §8.1)

| ID | 영역 | 설명 | 우회/상태 |
|----|------|------|----------|
| KI-001 | P0 | Win11 메모장 UI readback E2E 자동화 한계 | `scripts/spike/inject_ko_smoke.py --inject-auto` 수동 확인 |
| KI-002 | P4 | 모바일→허브 artifact 실기기 E2E 미검증 | 자동 ASGI E2E 통과; 수동 `docs/p4_mobile_e2e.md` |
| KI-003 | P4 | Cloudflare Tunnel 실환경 미검증 | `cloudflared` 설치 후 `scripts/smoke/tunnel_live_smoke.py` |
| KI-004 | P5 | NFR 실시간 1초 목표 — 모델·HW 의존 | `nfr_bench --all`로 추적 |
| KI-005 | C22 | 코드사인 미적용 — SmartScreen 경고 가능 | `build/SMARTSCREEN.txt` 참고 |
| KI-006 | README §14 | 기본 GPU/클라우드/배포 방향 미확정 | `DECISIONS.md` 잠정안 참고 |
| KI-007 | C16 | PySide6 6.11.x — 일부 Anaconda 3.10 환경에서 QtCore DLL 로드 실패 | `build/requirements-ci.txt` 6.8.3 pin 유지 |
| KI-008 | P4 | 청크 업로드 — 연속 index 검증·PWA 재시도 | 해결됨 (2026-07-05) |
| KI-009 | P4 | LAN 폴백은 Tunnel 실패 시만 0.0.0.0 | HTTP — 모바일 마이크 불가, 방화벽 확인 |
| KI-010 | P5 | SQLite 동시 접근 savepoint | 해결됨 — `Database._conn_lock` (2026-07-05) |
| KI-011 | P5 | verify_bundle stale dist | 해결됨 — `.venv`로 재빌드 (2026-07-05) |
| KI-012 | C15 | 청크 세션 in-memory — 게이트웨이 재시작 시 업로드 무효 | 단일 uvicorn worker 전제 (`server.py`) |
| KI-013 | C16 | Anaconda `pathlib` backport — PyInstaller 실패 | `build/build_env.py` 가드 + `.venv\\Scripts\\python.exe build/build.py` |

## 갱신 규칙

- 릴리스마다 해결된 항목은 제거하거나 "해결됨"으로 표기
- 신규 이슈는 ID를 순번으로 추가
