안녕okok안녕하세요 STT-AIO 테스트입니다.한글 주입 0% 손실 검증: 가나다라마바사 12345혼합문장 Mixed 한글English 日本語テスト 🎤# P3 Handoff → P4/P0 (갱신 2026-07-04)

## P3 완료 요약

| 구성요소 | 상태 | 비고 |
|----------|------|------|
| C16 Packaging | ● | PyInstaller onedir + `STT-AIO-Setup-*.exe` + installer_smoke |
| C18 ModelManager | ◐ | 다운로드 취소 UI |
| C22 Updater | ◐ | 수동 확인 (트레이·설정) |
| C15 RemoteGateway | ◐ | pairing·PWA·ingest·설정 UI·QR·SessionManager E2E·WebM(ffmpeg)·tunnel 스텁 |

## P4 진입 조건 (C15)

- [x] PIN/토큰 페어링 + PWA
- [x] WebM ingest (ffmpeg)
- [x] C14 원격 녹음 설정 탭 + 트레이 진입
- [x] QR 이미지 표시 (`app/ui/qr_util.py`, 설정 탭)
- [x] gateway E2E (`tests/remote/test_gateway_e2e.py`)
- [x] SessionManager 연동 (`tests/remote/test_gateway_session.py`)
- [ ] 모바일 브라우저 → 허브 artifact E2E (**실기기 — 사용자**) 
- [ ] Cloudflare Tunnel 실환경 검증 (cloudflared 설치 필요)

## P0 검증

- [x] `DECISIONS.md` 잠정 결정 문서
- [x] `record_p0_results.py` 자동 기록 (`P0-spike-results.md`)
- [x] UTF-16 + 클립보드 roundtrip (`--verify-clipboard`, `--verify-paste`)
- [x] SendInput UNICODE dispatch (`--inject-auto`, `test_unicode_input.py`)
- [x] STT 지연 실측 (`stt_latency.py`, tiny pass)
- [x] 실시간 경로 지연 벤치 (`realtime_latency.py`, VAD+STT 시뮬레이션)
- [x] Ollama 연결 (`ollama_smoke.py`)
- [x] 오디오 WER 회귀 + TTS fixtures (`baseline` reference-only, `STT_AIO_WER_LIVE=1`)
- [x] C2 pseudo-streaming + Groq/Deepgram + `transcribe_segment`→`run_stage1`
- [x] STT 전용 API 키(C19) + OpenAI/Groq `http_util` 재시도
- [ ] 메모장 UI readback E2E (Win11 메모장 자동화 한계 — 선택 수동 `--inject`)

```bash
python scripts/spike/inject_ko_smoke.py --inject-auto
python scripts/bench/realtime_latency.py --model tiny
python tests/fixtures/ko_wer/generate_fixtures.py
STT_AIO_WER_LIVE=1 python -m pytest tests/regression/ko_wer/test_wer_audio.py -m integration
```

## C1 VAD

- [x] `core/audio/vad.py` — energy 기본, silero 옵션 (`pip install stt-aio[vad]`)
- [x] 설정 `audio.vad_engine` + General 탭 UI
- [x] `tests/audio/test_vad.py`
- [x] `StreamCapture` 16k 리샘플 + `min_speech`/`max_segment` 적용
- [x] `tests/audio/test_stream_capture.py`

## C16 보강

- [x] `build/verify_bundle.py` CLI (`--app-dir`)
- [x] `build/verify_installer.py` + `build/find_iscc.py`
- [x] `VERSION.txt` + PE 버전 스모크 (`version_check.ps1`)
- [x] manifest merge + `finalize_manifest` 검증
- [x] `installer_smoke`: 업그레이드 재설치·제거 fail-fast
- [x] CI: `bundle_smoke -RequireExe` + installer smoke
- [x] C4→C8 pipeline export E2E (`test_pipeline_export_e2e.py`)

```bash
python build/build.py --portable
python build/build.py --installer --skip-pyinstaller --require-installer
powershell scripts/smoke/installer_smoke.ps1
```

## C2 §6.3 — Deepgram WebSocket 스트리밍 (2026-07-04)

- [x] `core/stt/deepgram_ws.py` — `_MinimalWebSocket` (표준 라이브러리 전용 RFC 6455) + `stream_via_websocket()`
- [x] `deepgram_transcribe.py` — `stream()` 구현 + `supports_streaming=True`
- [x] `registry.py` — `deepgram_stream` / `deepgram-stream` alias 추가
- [x] `tests/stt/test_deepgram_ws.py` — 15 tests (프레임 인코딩, 프로토콜, Provider 위임)

```bash
python -m pytest tests/stt/test_deepgram_ws.py -v   # 15 passed
```

## C2 WebSocket 버그픽스 + C22 §6.2 2단계 + P3 QA (2026-07-04)

### Deepgram WS 버그픽스
- [x] `assert` → `if ... raise RuntimeError` (PyInstaller 최적화 모드 대응)
- [x] `_DEFAULT_WS_HOST` → `_ws_host_from_base_url(base_url)` (커스텀 엔드포인트 일관성)
- [x] `stream()` docstring 오류 수정
- [x] 확장 길이 프레임(126/127) 테스트 추가
- [x] `recv_message` closed socket 처리 테스트 추가
- Total: 20 tests in `test_deepgram_ws.py`

### P3 QA 체크리스트 (계획서 §8 P3 필수 산출물)
- [x] `docs/qa_checklist.md` — PTT/온보딩/설정/파이프라인/Workbench/진단/패키징/업데이트/원격/NFR 10개 섹션

### C22 §6.2 2단계 — download + verify (P5)
- [x] `core/updater/verify.py` — SHA-256 체크섬 검증 (`verify_checksum`, `compute_sha256`)
- [x] `core/updater/downloader.py` — `download_update()` (임시파일 → 체크섬 → 원자 이동) + `apply_update()` (os.startfile)
- [x] `UpdateInfo` — `checksum_sha256`, `mandatory` 필드 추가 (checker.py)
- [x] `tests/updater/test_updater.py` — 17 tests (체크섬/매니페스트/다운로드/진행률/오류처리)

## P5 NFR + C22 UI 연동 (2026-07-04)

### P5 유휴 CPU — 패키지 exe 실측
- [x] `nfr_bench.py` — `find_packaged_exe()`, `bench_idle_cpu_packaged()` (프로세스 트리 CPU 샘플)
- [x] `nfr_targets.json` — `packaged_startup_sec` 추가
- [x] `--all` 리포트에 `idle_cpu_packaged` 섹션 포함
- [x] `tests/bench/test_nfr_bench.py` — packaged idle 테스트 4건 추가

```bash
python build/build.py --portable   # exe 빌드 후
python scripts/bench/nfr_bench.py --all --exe-path dist/STT-AIO/STT-AIO.exe
```

### C22 §6.2 UI 연동
- [x] `UpdateInfo.supports_direct_download` (URL + checksum)
- [x] `default_installer_path()` — `%APPDATA%\STT-AIO\updates\`
- [x] `UpdateDownloadTask` + `SettingsTaskRunner.run_update_download()`
- [x] `update_check.py` — 다운로드 진행 `QProgressDialog` + `apply_update()` 설치 실행

## P5/C22 계획서 잔여 보완 (2026-07-04)

### P5 NFR 통합·실측
- [x] `nfr_bench --all` — `realtime_latency`, `idle_cpu_packaged`(CPU+메모리), `summarize` 강화
- [x] `nfr_targets.json` — `realtime_target_ms`, `idle_memory_mb_max`
- [x] `devplans/phases/P5-nfr-results.md` — `record_nfr_results.py` 실행

### C22 코어
- [x] `core/updater/manifest.py` — 매니페스트 파싱 + `get_release_notes()`
- [x] `core/updater/version.py` — semver 비교 (`is_newer_version`)
- [x] `checker.py` — manifest 연동 + C20 `get_logger` 로깅

### C22 UI·설정
- [x] `update_check_logic.py` + 통합 테스트
- [x] mandatory UI / 다운로드 실패→브라우저 폴백 / 설치 후 `app.quit()`
- [x] `update.auto_check` (C11) + 설정 UI + 앱 시작 시 자동 확인
- [x] 업데이트 다운로드 lock (`try_begin_update_download`)

### P5 문서 산출물 (README §8.1)
- [x] `docs/release_checklist.md`
- [x] `docs/update_policy.md`
- [x] `docs/known_issues.md`

## C16 패키징 보강 (2026-07-04)

- [x] `pyinstaller.spec` — `collect_all('PySide6'/'shiboken6')`, UPX 비활성화
- [x] `verify_bundle.py` — `qwindows.dll` 플랫폼 플러그인 검증
- [x] `STT_AIO_NFR_BENCH=1` — NFR 벤치 시 키보드 훅 스킵 (`hotkey_manager`, `nfr_bench`)
- [x] `app/main.py` — frozen 빌드 PySide6 import 오류 상세 로그
- [x] PySide6 **6.8.3** pin (`build/requirements-ci.txt`) — 6.11.x DLL 호환 이슈 회피

```bash
.\.venv\Scripts\python.exe build/build.py
.\.venv\Scripts\python.exe scripts/bench/nfr_bench.py --all --exe-path dist/STT-AIO/STT-AIO.exe
```

## 다음 우선순위 (에이전트)

1. ~~P5 NFR 실측·문서~~ (2026-07-04)
2. ~~C22 계획서 잔여~~ (2026-07-04)
3. ~~C16 패키지 exe 기동 + packaged NFR~~ (2026-07-04)
4. ~~P4 자동 E2E·보안·터널 테스트~~ (2026-07-04) → `devplans/phases/P4-handoff.md`
5. P4 실기기 E2E (사용자) / Cloudflare Tunnel 실환경
6. C22 3단계 — 코드사인 후 자동 업데이트 (미결정)

테스트 기준선: `442 passed` (2026-07-04, UI 제외).

```bash
python scripts/bench/nfr_bench.py --all
python scripts/bench/record_nfr_results.py
```

## 사용자 요청 시

1. 스마트폰 QR → 원격 녹음 → 허브 artifact 확인
2. Cloudflare Tunnel 실환경 (cloudflared 설치 후)
3. README 14절 미결정 4건 (제품/배포 방향)
