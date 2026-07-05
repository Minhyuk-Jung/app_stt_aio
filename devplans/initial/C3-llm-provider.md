# C3. LLMProvider 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C3 |
| 이름 | LLMProvider (텍스트 가공) |
| 계층 | Core Engine |
| 관련 Phase | P0(연결확인), P2(교정/리포트), P3(확장) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
텍스트를 LLM으로 가공(2차 교정, 3차 리포트)하는 기능을 교체 가능한 Provider로 제공한다.

- 로컬(Ollama)·클라우드(OpenAI 호환) 구현체.
- 프롬프트 템플릿과 모드 메타데이터를 받아 완성 텍스트 생성.
- 스트리밍 토큰 출력 지원(가능한 경우).
- 능력/모델 목록 노출.

**책임이 아닌 것**: 프롬프트 프리셋 관리(C7 ModeManager), 단계 라우팅(C4 Pipeline), 결정적 규칙 후처리(C17).

---

## 2. 선택 근거와 대안 검토
- **Ollama + OpenAI 호환 조합**: 로컬은 Ollama가 설치/모델교체가 쉽고 HTTP API 단순. 클라우드는 OpenAI 호환 규격으로 OpenAI/Groq/OpenRouter/LM Studio/llama.cpp-server까지 하나의 어댑터로 흡수.
- **Anthropic 직접 API**: 초기에는 만들지 않고, OpenAI 호환 추상화가 자리잡은 뒤 별도 provider로 확장(대안 유지).
- **교정과 리포트를 같은 `complete()`로 처리**: 차이는 프롬프트/파라미터이므로 인터페이스를 단순화.

---

## 3. 공개 인터페이스 계약
공통 인터페이스 `LLMProvider`:
- `complete(request: LLMRequest) -> LLMResult`: 단일 완성.
- `stream(request) -> Iterator[LLMDelta]`: 토큰 스트리밍(지원 시).
- `list_models() -> [ModelInfo]`: 사용 가능 모델 조회(Ollama/클라우드).
- `capabilities() -> LLMCapabilities`.
- `test_connection() -> ConnResult`: 설정 UI의 연결 테스트용.

`LLMRequest` = { system_prompt, user_text, mode_id?, params{temperature, max_tokens, top_p}, stream? }.
`LLMResult` = { text, model, usage{prompt_tokens, completion_tokens}?, provider_id }.
`LLMCapabilities` = { supports_streaming, needs_network, context_window, cost_type }.

---

## 4. 입력/출력 데이터와 상태 전이
- 입력: 텍스트(1차 또는 2차 산출물) + 프롬프트.
- 출력: 가공된 텍스트(2차/3차 artifact).
- 상태: `ready → requesting → ready`(클라우드), 로컬은 모델 로드 지연 포함.
- 실패 시 이전 상태 유지, 오류 반환.

---

## 5. 의존 구성요소와 호출 관계
- **호출당하는 곳**: C4 Pipeline(stage2/stage3), C14 설정 UI(연결 테스트/모델 목록).
- **의존**: C19 Secrets(클라우드 키), C18 ModelManager(Ollama 모델 목록 조회 협조), C20 Logging.
- **입력 제공**: C7 ModeManager가 프롬프트를, C4가 대상 텍스트를 전달.

---

## 6. 내부 설계
### 6.1 구조
- `base.py`: 추상/데이터 타입/capabilities.
- `registry.py`: provider_id 팩토리.
- `ollama_local.py`: Ollama HTTP(`/api/generate` 또는 `/api/chat`) 연동, 모델 목록(`/api/tags`).
- `openai_compat.py`: base_url 구성으로 OpenAI/Groq/OpenRouter 등 처리(`/v1/chat/completions`).
- `errors.py`: 네트워크/인증/모델없음/컨텍스트초과.

### 6.2 처리 절차
1. C4가 stage에 맞는 프롬프트(C7)와 텍스트를 담아 `LLMRequest` 구성.
2. provider가 요청 포맷으로 변환(로컬/클라우드 규격 차이 흡수).
3. 스트리밍 여부에 따라 `complete` 또는 `stream` 실행.
4. 결과 텍스트 반환, usage/model 메타 부착.

### 6.3 프롬프트 취급
- provider는 프롬프트 "내용"을 만들지 않는다. 오직 전달·실행.
- system/user 분리를 지원하지 않는 로컬 모델은 단일 프롬프트로 합성.

### 6.4 컨텍스트 관리
- 3차 리포트는 입력이 길 수 있음 → 토큰 추정 후 컨텍스트 초과 시: (a) 분할 요약 후 통합, 또는 (b) 사용자 경고. 기본은 경고 + 분할 옵션.

---

## 7. 오류/폴백/재시도 정책
- **네트워크/타임아웃**: 지수 백오프 재시도(기본 2회).
- **인증 실패**: 재시도 금지, 키 재설정 안내.
- **모델 없음(Ollama)**: 설치/pull 안내 메시지.
- **컨텍스트 초과**: 분할 처리 또는 명확한 실패 사유.
- **Pipeline 연계 원칙**: LLM 실패는 전체 실패가 아니라 "직전 단계 산출물 유지 + 사용자 알림"(C4와 계약).
- **실시간 경로**: 기본적으로 LLM 미사용(지연 방지). 사용 시 명시적 옵트인.

---

## 8. 성능 목표
- 2차 교정(짧은 문단): 클라우드 저지연(Groq류) 1초 내외 목표, 로컬은 하드웨어 의존.
- 스트리밍 first-token 지연 최소화(UI에 진행 표시).

---

## 9. 보안/프라이버시 고려사항
- 클라우드 사용 시 텍스트가 외부로 전송됨을 명시.
- 키는 C19 경유, 로그 미기록.
- 프롬프트/원문 텍스트 로그 기본 미기록.

---

## 10. 테스트 항목
- 단위: 요청 매핑, 스트리밍 파싱, 예외 매핑(mock 서버).
- 통합: 실제 Ollama 연결, OpenAI 호환 엔드포인트 계약 테스트.
- 엣지: 빈 입력, 초장문(컨텍스트 초과), 서버 다운, 느린 응답.

---

## 11. 관련 Phase와 구현 범위
- **P0**: Ollama 연결 확인(가공은 미구현, 연결성만).
- **P2**: 교정/리포트 실제 가공, 스트리밍, 모델 목록/연결 테스트.
- **P3**: 리포트 품질 개선, 컨텍스트 분할.

---

## 12. 미결정 사항
- 기본 클라우드 provider/모델.
- 컨텍스트 초과 기본 처리(분할 vs 경고).
- system/user 분리 미지원 모델의 합성 규칙 세부.
- Anthropic 직접 provider 추가 시점.
