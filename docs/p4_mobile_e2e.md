# P4 모바일 실기기 E2E 가이드

> C15 §10 필수 산출물 — 폰 브라우저 녹음 → Windows 허브 artifact 확인 (수동)

## 사전 조건

1. Windows에서 STT-AIO 실행 (`dist/STT-AIO/STT-AIO.exe` 또는 `python -m app.main`)
2. (권장) [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) 설치 — 모바일 마이크는 HTTPS 필요
3. PC와 스마트폰이 동일 네트워크이거나 Tunnel 공개 URL 사용

## 절차

### 1. 원격 게이트웨이 시작

1. 설정 → **원격 녹음** 탭
2. **게이트웨이 시작** 클릭
3. Tunnel 사용 시 **Cloudflare Tunnel** 체크 (cloudflared 필요)
4. 표시된 **PIN**과 **QR 코드** 확인

### 2. 스마트폰 페어링

1. QR 스캔 또는 `https://…/pwa/` URL 접속
2. PC에 표시된 4자리 PIN 입력 → **페어링**
3. “페어링 완료” 메시지 확인

### 3. 녹음 및 업로드

1. **녹음 시작** → 짧게 말하기 → **녹음 정지**
2. “업로드 완료” 및 `session_id` JSON 확인

### 4. 허브에서 artifact 확인

1. PC STT-AIO **Workbench** 열기
2. 원격(`REMOTE`) 소스 세션 목록에서 방금 `session_id` 검색
3. Stage 1 artifact 텍스트가 생성되었는지 확인

## 실패 시

| 증상 | 확인 |
|------|------|
| 페어링 실패 | PIN 만료(10분) — 게이트웨이 재시작 |
| 마이크 권한 거부 | 브라우저 사이트 설정에서 마이크 허용 |
| 업로드 401 | 재페어링 (토큰 만료) |
| Tunnel URL 없음 | `python scripts/smoke/tunnel_check.py` 로 cloudflared 확인 |
| Tunnel 실패 + LAN URL만 표시 | **모바일 녹음 불가**(HTTP) — cloudflared 설치 후 Tunnel 재시도 |
| LAN 접속 불가 | Windows 방화벽에서 STT-AIO/Python 인바운드 허용 또는 포트(기본 8765) 예외 추가 |
| artifact 없음 | `%APPDATA%\\STT-AIO\\logs\\stt-aio.log` 확인 |

## 자동 검증 (개발/CI)

```bash
python -m pytest tests/remote -q
python scripts/smoke/record_p4_results.py
```

자동 테스트는 ASGI 시뮬레이션으로 pair → upload → DB artifact까지 검증합니다. 실기기 HTTPS·마이크 UX는 위 수동 절차로 확인하세요.
