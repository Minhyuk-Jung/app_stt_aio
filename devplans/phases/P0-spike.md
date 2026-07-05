# P0 Technical Spike (STT-AIO)

## 목적
비기능 요구사항(NFR) 실측 및 P0 리스크(한글 주입, STT 지연, VAD) 검증.

## 체크리스트

| 항목 | 스크립트 | 목표 |
|------|----------|------|
| 한글 주입 0% 손실 | `scripts/spike/inject_ko_smoke.py` | UTF-16 + 클립보드 roundtrip; `--inject`로 SendInput 수동 |
| 로컬 STT 지연 | `scripts/bench/stt_latency.py` | 짧은 문장 종료→텍스트 < 2s |
| VAD 세그먼트 | `scripts/bench/vad_segment.py` | 발화 종료 감지 ≤ hangover + frame_ms (30ms 프레임 양자화) |
| 한국어 WER | `tests/regression/ko_wer/test_wer_baseline.py` | 기준선 대비 회귀 없음 |

## 실행

```bash
python -m pytest tests/regression/ko_wer -q -m "not integration"
python scripts/spike/inject_ko_smoke.py --dry-run
python scripts/spike/inject_ko_smoke.py --verify-clipboard   # Windows
python scripts/bench/stt_latency.py
python scripts/bench/vad_segment.py
python scripts/bench/ko_wer_audio.py   # faster-whisper optional
python scripts/smoke/tunnel_check.py
```

## 결과 기록
측정 결과는 `devplans/phases/P0-spike-results.md`에 날짜·환경·수치를 기록한다.
