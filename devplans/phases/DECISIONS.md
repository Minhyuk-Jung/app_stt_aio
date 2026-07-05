# README §14 잠정 결정 (P0/P3 handoff)

> 상용화 전 재검토 필요. 코드 기본값과 문서의 단일 출처.

| # | 항목 | 잠정 결정 | 근거 |
|---|------|-----------|------|
| 1 | GPU / STT 모델 | **CPU 우선**, 기본 모델 `base`, 유저가 설정에서 변경 | 개인 개발·배포 단순화 |
| 2 | 기본 Provider | **로컬 우선** (faster-whisper + Ollama), 클라우드는 온보딩에서 선택 | README 프라이버시 기본 |
| 3 | 배포 목표 | **개인용 알파** — 코드서명·자동 업데이트 후순위, Tunnel 선택 | P3/P5 범위 |
| 4 | 제품명 | **STT-AIO** (코드명 유지) | 브랜딩 미확정 |

## 기술 잠정

| 영역 | 선택 | 대안 |
|------|------|------|
| VAD | `energy` 기본, `silero` 옵션 (`pip install stt-aio[vad]`) | WebRTC VAD |
| 원격 접속 | 로컬 HTTP + 선택 Tunnel | 중앙 중계 서버 |
| WebM | ffmpeg PATH 의존 | 서버 측 pydub |

## 다음 확정 회의 안건

- 상용 전환 시 GPU 번들·기본 모델 크기
- 온보딩 필수 단계 최종 정책

## P6 잠정 (2026-07-05)

| 항목 | 잠정 결정 |
|------|-----------|
| 매니페스트 호스팅 | **GitHub Releases** (`release.yml`, `update-manifest.json` asset) |
| 릴리스 태그 | `v{semver}` — `build-manifest.json` version과 **일치 필수** (`verify_release_tag.py`) |
