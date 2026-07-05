# C2. STTProvider 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C2 |
| 이름 | STTProvider (음성→텍스트) |
| 계층 | Core Engine |
| 관련 Phase | P0(로컬 검증), P1(로컬 배치), P2(클라우드/스트림) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
오디오를 텍스트로 변환하는 기능을 **교체 가능한 Provider 인터페이스** 뒤에 제공한다.

- 배치 변환(오디오 버퍼 전체 → 텍스트).
- 스트리밍 변환(오디오 청크 → 부분/확정 세그먼트).
- 로컬(faster-whisper)·클라우드(Groq/Deepgram/OpenAI) 구현체.
- 각 구현체의 능력(capabilities)과 상태를 표준화하여 상위(C4)가 동일하게 소비.

**책임이 아닌 것**: 오디오 캡처(C1), 텍스트 후처리/정규화(C17), LLM 가공(C3).

---

## 2. 선택 근거와 대안 검토
- **추상화 우선**: 구현체가 하나여도 인터페이스를 먼저 둔다(README 원칙). 로컬↔클라우드 스위칭이 제품 핵심 요구.
- **로컬 기본 = faster-whisper**: CTranslate2 기반으로 순정 whisper보다 가볍고 빠르며 GPU/CPU 선택 가능. 대안 `whisper.cpp`(더 가벼움, CPU 친화)는 P0 비교 후 보조 옵션으로 유지.
- **클라우드**: OpenAI 호환 전사 API를 우선 어댑터로, Deepgram/Groq는 각자 SDK/HTTP 어댑터. 진짜 스트리밍이 필요하면 Deepgram/Groq 우선.
- **hotwords/초기 프롬프트**: faster-whisper의 `initial_prompt`/hotwords로 한국어 고유명사 인식 보정. 미지원 엔진은 C17에서 보정.

---

## 3. 공개 인터페이스 계약
공통 인터페이스 `STTProvider`:
- `transcribe(audio: AudioBuffer, options) -> STTResult`: 배치 변환.
- `stream(audio_chunks, options) -> Iterator[STTSegment]`: 스트리밍 변환(지원 시).
- `capabilities() -> STTCapabilities`: 지원 기능/제약.
- `warmup()`: 모델 사전 로드(선택).
- `close()`: 리소스 해제.

`STTCapabilities` = { supports_streaming, languages, max_audio_sec, needs_network, cost_type[free|local|paid], gpu_optional }.

`STTResult` = { text, language, segments[{start,end,text,confidence?}], duration_ms, provider_id }.
`STTSegment` = { text, is_final, start_ms, end_ms }.

`options` = { language(고정 또는 auto), initial_prompt/hotwords, beam_size, temperature, task=transcribe }.

---

## 4. 입력/출력 데이터와 상태 전이
- 입력: C1의 `AudioBuffer`(배치) 또는 청크 스트림.
- 출력: `STTResult`/`STTSegment`.
- 상태: `unloaded → loading(model) → ready → busy(transcribing) → ready`. 클라우드는 `ready → requesting → ready`.
- 실패 시 `ready` 유지하고 오류 반환(모델 상태 훼손 금지).

---

## 5. 의존 구성요소와 호출 관계
- **호출당하는 곳**: C4 Pipeline(stage1).
- **의존**: C18 ModelManager(로컬 모델 경로/존재 확인/다운로드), C19 Secrets(클라우드 API 키), C20 Logging.
- **하위 전달**: 결과 텍스트는 C17 TextProcessor → C5 Injector/저장 경로로.

---

## 6. 내부 설계
### 6.1 구조
- `base.py`: `STTProvider` 추상, 공통 데이터 타입, capabilities.
- `registry.py`: provider_id → 구현체 팩토리 등록/생성.
- `faster_whisper_local.py`: 로컬 구현(모델 로드/디바이스 선택/배치·유사스트리밍).
- `openai_cloud.py`, `deepgram_cloud.py`, `groq_cloud.py`: 클라우드 어댑터.
- `errors.py`: 표준 예외(네트워크, 인증, 모델 없음, 포맷).

### 6.2 로컬 구현 절차(배치)
1. ModelManager로 활성 모델 경로/존재 확인(없으면 오류→상위가 다운로드 유도).
2. 최초 호출 시 모델 로드(디바이스=auto/gpu/cpu, compute_type 선택).
3. `AudioBuffer`를 엔진 입력 형식으로 전달, 언어/옵션 적용.
4. 세그먼트 수집 → `STTResult` 조립.

### 6.3 스트리밍 전략
- 진짜 스트리밍 지원 클라우드는 청크 전송 → 부분 결과 수신.
- faster-whisper는 네이티브 스트리밍이 없으므로 **VAD 세그먼트 단위 유사 스트리밍**(C1이 확정한 세그먼트를 배치 변환하여 `is_final=True`로 방출).
- 부분 미확정(partial) 표시가 필요하면 짧은 window 재변환 방식은 P2에서 성능 보고 결정.

### 6.4 provider 전환
- 설정(C11)에서 활성 provider_id + provider별 옵션 관리.
- 전환 시 이전 provider `close()` 후 새 provider 생성. 모델 로드는 지연(lazy).

---

## 7. 오류/폴백/재시도 정책
- **모델 없음(로컬)**: 오류 코드 반환 → 상위(UI/Onboarding)가 다운로드 유도. 자동 다운로드는 C18 정책.
- **네트워크/타임아웃(클라우드)**: 지수 백오프 재시도(최대 N회, 기본 2회). 최종 실패 시 오류 반환.
- **인증 실패(401)**: 재시도 금지, 키 재설정 안내.
- **폴백 규칙**: 설정에 "클라우드 실패 시 로컬로 폴백" 옵션(가능한 경우). 폴백 발생 시 사용자에게 토스트 고지.
- **오디오 과길이**: `max_audio_sec` 초과 시 분할 변환 또는 거부(정책 명시).

---

## 8. 성능 목표
- 로컬 배치(짧은 문장, 권장 모델): 발화 종료 후 2초 이내(NFR).
- 클라우드 왕복: 네트워크 제외 오버헤드 최소화(스트리밍 시 세그먼트 1초 이내 목표).
- 모델 웜업은 앱 유휴 시 백그라운드로 수행하여 첫 사용 지연 완화(선택).

---

## 9. 보안/프라이버시 고려사항
- 클라우드 사용 시 오디오가 외부로 전송됨을 UI에 명시(C11/보안 정책).
- API 키는 C19를 통해서만 조회, 로그에 남기지 않음.
- 전사 원문 텍스트는 로그 기본 미기록(진단 시 옵트인).

---

## 10. 테스트 항목
- 단위: capabilities 정확성, 옵션 매핑, 결과 스키마, 예외 매핑(mock).
- 통합: 실제 로컬 모델로 한국어 샘플 배치 변환, 클라우드 어댑터 계약 테스트(mock/실키 분리).
- 회귀: 한국어 고정 샘플셋 WER 추적(12절 QA).
- 엣지: 무음 오디오, 초장문, 잡음, 언어 오탐.

---

## 11. 관련 Phase와 구현 범위
- **P0**: faster-whisper 로컬 배치 동작 + 한국어 정확도 감 잡기.
- **P1**: 로컬 배치 provider 안정화, registry/base 확정.
- **P2**: 클라우드 어댑터, capabilities 기반 UI 노출, 유사 스트리밍.
- **P5**: 성능/정확도 튜닝.

---

## 12. 미결정 사항
- 기본 로컬 모델 크기(GPU 유무 결정에 종속, README 14절).
- partial(미확정) 텍스트 표시 여부.
- 클라우드 기본 provider 선택(Groq/Deepgram/OpenAI).
- 클라우드→로컬 자동 폴백 기본값.
