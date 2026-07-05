# STT-AIO 릴리스 체크리스트

> P5 DoD 필수 산출물 (`README.md` §8.1)

릴리스 전 아래 항목을 확인하고 기록합니다. 상세 수동 시나리오는 `docs/qa_checklist.md`를 참고하세요.

## 빌드·패키징 (C16)

| # | 항목 | 확인 |
|---|------|------|
| 1 | `python build/build.py --portable` 성공 | ☑ |
| 2 | `python build/build.py --installer --require-installer` 성공 | ☑ |
| 3 | `scripts/smoke/installer_smoke.ps1` 통과 | ☑ |
| 4 | `build-manifest.json` 버전·아티팩트 검증 | ☐ (`python build/verify_installer.py`) |
| 4b | C22 `update-manifest.json` 생성 | ☐ (`python build/generate_update_manifest.py --download-url …`) |
| 5 | CI `build.yml` 정의 검증 (`verify_ci_workflow.py`) | ☑ |
| 5b | GitHub Actions `build.yml` 최근 run green | ☐ |

## 테스트

| # | 항목 | 확인 |
|---|------|------|
| 6 | `pytest tests/ --ignore=tests/ui` 통과 | ☑ |
| 7 | 한국어 WER 회귀 (`STT_AIO_WER_LIVE=1` 선택) | ☑ |

## NFR (P5)

| # | 항목 | 확인 |
|---|------|------|
| 8 | `python scripts/bench/nfr_bench.py --all` 실행·기록 | ☑ |
| 9 | `devplans/phases/P5-nfr-results.md` 갱신 | ☑ |
| 10 | 패키지 exe 유휴 CPU/메모리 목표 검토 | ☑ |

## 업데이트 (C22)

| # | 항목 | 확인 |
|---|------|------|
| 11 | 매니페스트 URL·checksum·download_url 게시 | ☑ (`scripts/release/prepare_release_manifest.py`) |
| 12 | 수동 업데이트 확인 UI 동작 | ☐ |
| 13 | 다운로드·검증·설치 실행 흐름 | ☐ |

## 배포 기록

| 항목 | 내용 |
|------|------|
| 버전 | |
| 날짜 | |
| 빌드 담당 | |
| 서명/코드사인 | (해당 시) |
| 비고 | |
