# STT-AIO 개발 마스터 계획서

| 항목 | 내용 |
|------|------|
| 문서 버전 | v0.3 (구성요소 검증 반영) |
| 상태 | 구성요소별 상세 계획 작성 전 기준 문서 |
| 최종 수정 | 2026-07-04 |
| 범위 | 프로젝트 전체 조망 + 하위 문서 인덱스 |

> 이 문서는 프로젝트 전체를 조망하는 **마스터 인덱스**입니다.
> 단계별(Phase)/구성요소별(Component) 상세 계획은 각 하위 문서로 분리 작성하며,
> 본 문서 13절 "문서 체계"에서 링크로 관리합니다.
> 개별 문서를 나중에 모두 작성할 것을 전제로, 본 문서는 **구성요소 간 상호관계**와
> **단계 × 구성요소 매트릭스**를 중심으로 구성했습니다.
> 또한 각 구성요소 상세 계획서 작성 시 누락이 없도록 **선택 근거, 대안, 인터페이스, 구현 주의점**을 함께 기록합니다.

---

## 1. 프로젝트 정의

### 1.1 한 줄 정의
마이크 음성을 텍스트로 변환하고(STT), LLM으로 다듬은 뒤(교정·리포트), Windows 커서 위치에 자동 입력하는 **로컬 우선 AI 음성 문서화 도구**.

### 1.2 비전
Windows 기본 받아쓰기(Win+H)의 UX를 계승하되, **선택형 3단계 가공 파이프라인**과 **문서 산출(txt/md/docx)** 까지 갖춘 "AI 업무 비서".

### 1.3 차별화 포인트 (벤치마크 기반)
- **한국어 완성도**: 한글 IME 우회 유니코드 주입 + 한국어 교정/리포트 프롬프트 튜닝 + 한국어 띄어쓰기/문장부호 정규화.
- **명시적 3단계 파이프라인 + 중간 산출물 관리/재가공**: 1/2/3차 결과를 각각 보존하고 골라서 재가공·내보내기.
- **문서화 출력**: 회의록/보고서 docx·md 양식 출력.

### 1.4 벤치마크 레퍼런스
- 골격/모드/Provider: VOCIX, GigaWhisper, WhisPaste
- 실시간 VAD·SendInput 주입: Murmur
- 로컬 STT 표준: faster-whisper(CTranslate2), Silero VAD
- 원격 마이크 위성: airmic (QR + 브라우저 + WiFi/릴레이)
- 상용 기준선: Superwhisper(로컬·모드·회의록), Wispr Flow(클라우드·자동편집)

---

## 2. 범위(Scope)

### 2.1 In scope
- Windows 데스크톱 앱(허브): STT/LLM/커서주입/문서출력/설정
- 실시간 변환 모드 + 단위 녹음 모드
- STT/LLM 로컬(faster-whisper/Ollama) ↔ 클라우드(Groq/OpenAI/Deepgram) 스위칭
- 모바일/웹 위성: **녹음 전용** (타 앱 입력 기능 없음)

### 2.2 Out of scope (→ 15절 백로그로 관리)
- 모바일/웹에서의 타 앱 텍스트 주입 (OS 제약)
- 화자 분리(diarization), 자동 번역, 팀/동기화 기능

---

## 3. 비기능 요구사항(NFR) — 측정 가능한 목표

| 항목 | 목표 | 비고 |
|------|------|------|
| 단위 녹음 지연 | 발화 종료 → 주입까지 로컬 STT 2초 이내(짧은 문장) | 모델·하드웨어 의존 |
| 실시간 지연 | 발화 세그먼트 종료 → 주입까지 1초 이내 | 1차만 즉시 |
| 한글 주입 정확도 | 조합/특수문자 손실 0% | P0 필수 검증 |
| STT 정확도(한국어) | 회귀 테스트셋 대비 WER 기준선 유지 | 12절 QA |
| 유휴 리소스 | 대기 시 CPU 1% 미만, 메모리 최소화 | 상시 트레이 |
| 앱 시작 시간 | 콜드 스타트 3초 이내(모델 지연 로드) | 모델은 사용 시 로드 |
| 크래시 복구 | 비정상 종료 후 세션/설정 보존 | Store 트랜잭션 |

---

## 4. 시스템 아키텍처 개요

### 4.1 레이어
```
UI(PySide6) → Application/Orchestrator → Core Engine → (선택) Remote Gateway
                                       ↘ Cross-cutting(로깅·보안·설정)
```
- **UI Layer**: Tray, Overlay Bar, Workbench, Settings, Mode 관리, History, Onboarding
- **Application**: HotkeyManager, PipelineController, SessionManager, ModeManager, Config
- **Core Engine(UI 독립)**: AudioCapture(VAD), STTProvider*, LLMProvider*, TextProcessor, Injector, Exporter, Store, ModelManager
- **Cross-cutting**: Secrets/Security, Logging/Diagnostics
- **Remote Gateway(Phase 4)**: FastAPI + PWA + Tunnel

`* = 교체 가능한 추상 인터페이스`

### 4.2 핵심 설계 원칙
1. Core Engine은 PySide6에 의존하지 않는다(재사용성: CLI·서버·테스트 공용).
2. 모든 외부 의존(STT/LLM)은 Provider 인터페이스 뒤에 둔다.
3. "모드 = 프롬프트 프리셋"이 파이프라인 제어의 단위다.
4. 중간 산출물(1/2/3차)은 DB에 각각 저장한다.
5. 한국어 주입 안정성을 최우선으로 한다.
6. 비밀정보는 평문 저장하지 않는다(OS 보안 저장소 사용).

---

## 5. 구성요소 카탈로그 (Component Catalog)

각 구성요소는 이후 개별 상세 문서(`devplans/components/<ID>-*.md`)로 작성한다.

### 5.1 Core Engine
| ID | 구성요소 | 책임 | 주요 의존 |
|----|----------|------|-----------|
| C1 | AudioCapture | WASAPI 캡처, 16kHz 모노 변환, 링버퍼, Silero VAD 세그먼트 | - |
| C2 | STTProvider | 음성→텍스트(배치/스트리밍), 로컬·클라우드 구현체, hotwords | C1, C18 |
| C3 | LLMProvider | 텍스트 가공(교정/리포트), 로컬·클라우드 구현체 | C19 |
| C4 | Pipeline | 1→2→3차 라우팅, 재가공, 처리 큐 오케스트레이션 | C2,C3,C6,C7,C17 |
| C5 | Injector | 커서 주입(SendInput UNICODE/Clipboard), 한글 처리, 클립보드 복원 | - |
| C6 | Store | SQLite: 세션/산출물/모드/설정, 마이그레이션 | - |
| C7 | ModeManager | 모드(프롬프트 프리셋) CRUD, 기본 모드 시드 | C6 |
| C8 | Exporter | txt/md/docx 내보내기, 템플릿 | C6 |
| C17 | TextProcessor | 스니펫 확장, 사용자 사전, 한국어 정규화(주입 전 후처리) | C6 |
| C18 | ModelManager | Whisper 모델 목록/다운로드/캐시/선택, Ollama 모델 조회 | C20 |

### 5.2 Application 계층
| ID | 구성요소 | 책임 | 주요 의존 |
|----|----------|------|-----------|
| C9 | HotkeyManager | 전역 핫키(PTT/토글), 취소(Esc)/자동전송(Enter), 충돌 감지 | - |
| C10 | SessionManager | 세션 수명주기, 소스(realtime/batch/remote), 처리 중 재입력 큐 정책 | C6, C4 |
| C11 | Config | 설정 스키마/영속화, 마이크 장치 선택, 사용자 데이터 경로 | C6 |
| C19 | Secrets/Security | API 키 저장(Windows DPAPI/Credential Manager), 오디오 보관·삭제 정책 | - |
| C20 | Logging/Diagnostics | 구조화 로깅, 진단 zip export, 텔레메트리(기본 OFF) | - |

### 5.3 UI 계층
| ID | 구성요소 | 책임 | 주요 의존 |
|----|----------|------|-----------|
| C12 | UI-Tray/Overlay | 트레이 메뉴, 오버레이 바(파형/상태), DPI 대응 | App 계층 |
| C13 | UI-Workbench | 작업대: 산출물 조회/편집/재가공/내보내기 | C4,C6,C8 |
| C14 | UI-Settings/Modes | 설정창, Provider·키·마이크 설정, 모드 관리 UI | C7,C11,C18,C19 |
| C21 | UI-Onboarding | 최초실행 마법사: 모델 다운로드·Provider·권한·핫키 안내 | C18,C11,C19 |

### 5.4 통합/배포 계층
| ID | 구성요소 | 책임 | 주요 의존 |
|----|----------|------|-----------|
| C15 | RemoteGateway | FastAPI+PWA+Tunnel, 폰 녹음 수신, 페어링(QR/PIN) | C1,C10,C4,C19 |
| C16 | Packaging | PyInstaller/Nuitka + Inno Setup, CI 빌드 | 전체 |
| C22 | Updater | 버전 확인/업데이트(단계적), 릴리스 노트 | C20 |

### 5.5 구성요소 선택 검증 요약
현재 구성요소 분리는 적절하다. 이유는 다음과 같다.

- **Audio/STT/LLM/Pipeline/Injector를 분리한 결정은 타당**하다. 음성 입력, 모델 추론, 텍스트 가공, OS 입력 주입은 장애 원인·성능 특성·테스트 방식이 모두 다르므로 한 모듈에 묶으면 유지보수가 어려워진다.
- **TextProcessor를 별도 구성요소로 둔 결정은 필수**다. 한국어 띄어쓰기, 숫자·문장부호 정규화, 사용자 사전, 스니펫 확장은 STT도 LLM도 아닌 중간 후처리 책임이다.
- **ModelManager를 Packaging에서 분리한 결정은 적절**하다. 모델 다운로드·캐시·검증은 설치 시점이 아니라 런타임에도 반복되는 기능이다.
- **Secrets/Security와 Logging/Diagnostics를 교차 관심사로 둔 결정은 적절**하다. API 키, 로그 마스킹, 진단 파일은 거의 모든 계층과 관련되며 개별 기능에 섞으면 누락 위험이 크다.
- **RemoteGateway를 후순위 독립 구성요소로 둔 결정은 적절**하다. 모바일/웹 위성은 핵심 가치가 아니라 확장 가치이므로 Windows 허브가 안정된 뒤 붙인다.

다만 이후 상세 계획 작성 시 아래 보완 원칙을 지켜야 한다.

- **C6 Store는 너무 늦게 만들면 안 된다.** P1부터 최소 세션/설정 저장 구조를 준비해야 이후 Pipeline, Workbench, Exporter가 흔들리지 않는다.
- **C19 Secrets/Security는 P3까지 미루지 않는다.** 클라우드 Provider가 들어가는 P2부터 API 키 저장 방식과 로그 마스킹을 최소 구현해야 한다.
- **C18 ModelManager는 P0/P1에서 최소 기능이 필요하다.** 모델 경로 지정·존재 확인·다운로드 실패 메시지는 초기부터 사용자 경험에 직접 영향을 준다.
- **C20 Logging/Diagnostics는 P0부터 얇게 시작한다.** 오디오 장치, 모델 로딩, 주입 실패는 재현이 어려워 초기에 로그 기반을 깔아야 한다.

### 5.6 구성요소별 상세 계획서에 반드시 전달할 정보
각 `devplans/components/*.md` 문서는 아래 항목을 반드시 포함한다. 이 항목들은 실제 구현자가 해당 문서만 읽고 작업을 시작할 수 있게 하기 위한 최소 정보다.

| 항목 | 작성 내용 |
|------|-----------|
| 선택 근거 | 왜 이 방식/라이브러리/경계를 선택했는지 |
| 대안 검토 | 고려했으나 채택하지 않은 대안과 이유 |
| 공개 인터페이스 | 다른 구성요소가 호출할 함수/클래스/이벤트 계약 |
| 입력/출력 데이터 | 타입, 단위, 저장 위치, 실패 시 반환 정책 |
| 상태 전이 | idle/recording/processing/error 등 상태와 전환 조건 |
| 오류/폴백 | 실패 시 사용자 알림, 자동 재시도, raw fallback 여부 |
| 성능 목표 | 지연 시간, 메모리, 파일 크기, 동시성 요구 |
| 테스트 기준 | 단위/통합/E2E 테스트 항목과 수용 기준 |
| 보안/프라이버시 | 민감 정보, 로그 마스킹, 오디오/텍스트 보관 여부 |
| 관련 Phase | 어느 Phase에서 어떤 범위까지 구현하는지 |

### 5.7 구성요소별 개발 방향 (요약)

#### C1 AudioCapture
- **선택 검증**: Windows 전용 앱이므로 WASAPI 기반 캡처가 적절하다. Python에서는 `sounddevice`/`pyaudio` 계열을 검증하되, 장치 호환성과 패키징 안정성을 P0에서 비교한다.
- **핵심 계약**: 16kHz mono PCM을 표준 내부 포맷으로 제공한다. Provider별 요구 포맷 변환은 C1 또는 C2 경계에서 명확히 정한다.
- **주의점**: 실시간 모드와 단위 녹음 모드는 같은 캡처 기반을 공유하되 버퍼링 전략이 다르다. VAD는 녹음 종료 판단을 보조하고, 강제 종료는 HotkeyManager가 우선권을 가진다.

#### C2 STTProvider
- **선택 검증**: 로컬 기본은 `faster-whisper`가 적절하다. `whisper.cpp`는 배포 용량과 CPU 친화성 장점이 있으므로 대안으로 남긴다. 클라우드는 Groq/Deepgram/OpenAI를 OpenAI 호환 또는 Provider별 어댑터로 감싼다.
- **핵심 계약**: 배치 `transcribe()`와 실시간 `stream()`을 분리한다. 모든 구현체는 `capabilities()`로 스트리밍 가능 여부, 지원 언어, 예상 지연, 비용 유형을 반환한다.
- **주의점**: 한국어 hotwords/사용자 사전은 STT 엔진이 지원하면 C2에서 사용하고, 지원하지 않으면 C17에서 보정한다.

#### C3 LLMProvider
- **선택 검증**: Ollama + OpenAI 호환 API 조합이 적절하다. Claude/Anthropic은 초기에 직접 구현하지 않고 OpenAI 호환 추상화 이후 별도 Provider로 확장한다.
- **핵심 계약**: 교정과 리포트는 같은 `complete()`를 쓰되, prompt template과 mode metadata를 명확히 넘긴다.
- **주의점**: LLM 실패 시 Pipeline은 전체 실패가 아니라 "이전 단계 산출물 유지 + 사용자 알림"으로 동작한다. 실시간 입력 경로에서는 기본적으로 LLM을 끼우지 않는다.

#### C4 Pipeline
- **선택 검증**: Pipeline을 독립 구성요소로 둔 결정은 매우 중요하다. UI, 원격 위성, CLI 테스트가 모두 같은 처리 흐름을 재사용해야 한다.
- **핵심 계약**: 입력은 audio 또는 기존 artifact, 출력은 stage별 artifact 목록이다. stage 실행 전후에 Store 저장과 이벤트 발행을 수행한다.
- **주의점**: "주입할 단계(inject_stage)"와 "생성할 목표 단계(target_stage)"는 다르다. 예를 들어 회의록 모드는 3차까지 생성하지만 커서에는 아무것도 넣지 않을 수 있다.

#### C5 Injector
- **선택 검증**: SendInput UNICODE 우선, Clipboard 폴백 전략이 적절하다. 한글 IME 깨짐과 클립보드 훼손을 동시에 고려한 균형안이다.
- **핵심 계약**: `inject(text, method)`는 성공/실패와 실제 사용한 전략을 반환한다.
- **주의점**: 대량 텍스트는 Clipboard가 빠르고, 실시간 청크는 SendInput이 적합하다. 클립보드 방식은 기존 클립보드 백업/복원 실패까지 로그로 남긴다.

#### C6 Store
- **선택 검증**: SQLite가 적절하다. 로컬 단일 사용자 앱이고 세션/산출물/설정 트랜잭션이 필요하다.
- **핵심 계약**: 세션, artifact, mode, dictionary, setting을 저장한다. 마이그레이션 버전을 반드시 둔다.
- **주의점**: 오디오 파일은 DB에 직접 넣지 않고 파일 경로를 저장한다. 민감 정보(API key)는 저장하지 않는다.

#### C7 ModeManager
- **선택 검증**: 모드 시스템은 이 제품의 UX 핵심이다. Superwhisper/Kalam류의 custom mode를 한국어 문서화 흐름에 맞게 확장한다.
- **핵심 계약**: mode는 target_stage, inject_stage, correction_prompt, report_prompt, provider override를 가질 수 있다.
- **주의점**: 기본 모드(빠른 받아쓰기/문장 다듬기/회의록/보고서)를 seed로 제공하되 사용자가 편집 가능해야 한다.

#### C8 Exporter
- **선택 검증**: txt/md/docx 분리는 요구사항에 맞다. docx는 `python-docx`, md/txt는 템플릿 기반 문자열 생성으로 충분하다.
- **핵심 계약**: session 또는 artifact 목록을 받아 지정 포맷 파일을 생성한다.
- **주의점**: 3차 리포트는 docx heading/list/table 스타일을 고려한다. 파일명 규칙과 중복 처리 정책을 정한다.

#### C9 HotkeyManager
- **선택 검증**: 전역 핫키는 Windows 앱의 핵심 UX다. PTT와 Toggle을 모두 지원하는 것이 벤치마크 표준과 맞다.
- **핵심 계약**: record_start, record_stop, cancel, auto_send 이벤트를 발생시킨다.
- **주의점**: 관리자 권한 앱 대상 입력 제약, 핫키 충돌, 키 반복 이벤트를 반드시 처리한다.

#### C10 SessionManager
- **선택 검증**: 세션 수명주기를 별도로 둬야 batch/realtime/remote를 같은 개념으로 관리할 수 있다.
- **핵심 계약**: session 생성, 상태 변경, 취소, 완료, 재처리 요청을 관리한다.
- **주의점**: 처리 중 새 녹음이 들어오면 큐잉/취소/무시 중 정책을 명확히 한다. 기본값은 큐잉이다.

#### C11 Config
- **선택 검증**: 설정은 Store와 분리된 도메인 계층이 필요하다. UI가 직접 DB key를 다루면 설정 변경 영향 범위가 커진다.
- **핵심 계약**: 타입이 있는 설정 스키마, 기본값, validation, migration을 제공한다.
- **주의점**: 비민감 설정만 파일/DB에 저장한다. 민감 설정은 C19를 통해 참조한다.

#### C12 UI-Tray/Overlay
- **선택 검증**: 심플 GUI 요구와 Windows 받아쓰기 UX를 고려하면 트레이 + 작은 오버레이가 적절하다.
- **핵심 계약**: 앱 상태(recording/processing/error), 파형, 빠른 모드 변경을 보여준다.
- **주의점**: UI는 처리 로직을 갖지 않고 Application 이벤트만 구독한다. DPI/다중 모니터를 고려한다.

#### C13 UI-Workbench
- **선택 검증**: 1/2/3차 산출물 관리와 재가공은 기존 받아쓰기 앱과의 차별점이므로 별도 작업대가 필요하다.
- **핵심 계약**: 세션 목록, artifact 비교/편집, reprocess, export 액션을 제공한다.
- **주의점**: 사용자가 1차 산출물을 수정한 뒤 2차/3차 재가공할 수 있어야 한다.

#### C14 UI-Settings/Modes
- **선택 검증**: Provider, 모델, API 키, 프롬프트 모드는 복잡도가 높아 별도 설정 화면이 필요하다.
- **핵심 계약**: Provider 연결 테스트, 모델 목록 조회, 모드 CRUD, hotkey 설정을 제공한다.
- **주의점**: 연결 테스트 실패 사유를 사용자 언어로 보여준다. API 키 입력은 C19에 위임한다.

#### C15 RemoteGateway
- **선택 검증**: 모바일/웹은 녹음 전용으로 축소한 판단이 적절하다. FastAPI + PWA + Cloudflare Tunnel은 HTTPS와 QR 접속 문제를 현실적으로 해결한다.
- **핵심 계약**: 페어링된 클라이언트의 audio blob/stream을 SessionManager에 전달한다.
- **주의점**: P4 이전에는 구현하지 않는다. 인증 없는 업로드, 터널 URL 노출, 대용량 파일 제한을 반드시 다룬다.

#### C16 Packaging
- **선택 검증**: Python 생태계에서는 PyInstaller가 안정적이고, Nuitka는 성능/난독화 측면 대안이다. 설치본은 Inno Setup이 현실적이다.
- **핵심 계약**: Windows 설치본, 포터블 빌드(선택), 모델 제외/포함 정책을 관리한다.
- **주의점**: Whisper 모델을 설치본에 무조건 포함하지 않는다. 최초실행 다운로드와 오프라인 모델 경로 지정 옵션을 제공한다.

#### C17 TextProcessor
- **선택 검증**: 한국어 품질과 업무용 편의성을 위해 독립 구성요소가 필요하다.
- **핵심 계약**: STT 결과를 받아 정규화, 사전 치환, 스니펫 확장, stage별 전처리를 수행한다.
- **주의점**: LLM 교정과 중복되지 않도록 deterministic rule 위주로 제한한다. 과도한 자동 수정은 사용자가 끌 수 있어야 한다.

#### C18 ModelManager
- **선택 검증**: 모델 다운로드/검증/캐시는 런타임 기능이므로 별도 관리가 적절하다.
- **핵심 계약**: 모델 목록, 다운로드 상태, checksum 검증, 활성 모델 선택, Ollama 모델 조회를 제공한다.
- **주의점**: 다운로드 중단/재개, 디스크 공간 부족, 프록시/인증서 문제를 오류 메시지에 반영한다.

#### C19 Secrets/Security
- **선택 검증**: 클라우드 Provider를 지원하는 순간 필수 구성요소다.
- **핵심 계약**: secret 저장/조회/삭제, 로그 마스킹, 오디오 보관 정책 검증을 제공한다.
- **주의점**: 개발 편의를 위해 평문 fallback을 만들지 않는다. 테스트에서는 mock secret store를 사용한다.

#### C20 Logging/Diagnostics
- **선택 검증**: 음성/주입/모델 문제는 사용자 환경 의존성이 커서 진단 기능이 필요하다.
- **핵심 계약**: structured log, error event, diagnostic export(zip)를 제공한다.
- **주의점**: 로그에는 API 키, 원문 텍스트, 오디오 경로 등 민감 정보가 들어가지 않도록 기본 마스킹한다.

#### C21 UI-Onboarding
- **선택 검증**: 모델 다운로드, API 키, 권한, 핫키 등 첫 실행 장벽이 높아 온보딩이 필요하다.
- **핵심 계약**: 첫 실행 시 Provider 선택, 모델 준비, 마이크 테스트, 주입 테스트를 순서대로 안내한다.
- **주의점**: 온보딩 없이도 설정 화면에서 같은 작업을 다시 수행할 수 있어야 한다.

#### C22 Updater
- **선택 검증**: 초기 MVP에는 불필요하지만 배포/상용 단계에는 필요하다. 독립 구성요소로 후순위 유지가 적절하다.
- **핵심 계약**: 버전 확인, 릴리스 노트 표시, 업데이트 다운로드/실행을 담당한다.
- **주의점**: 코드사인/무결성 검증 전에는 자동 설치보다 수동 다운로드 안내가 안전하다.

---

## 6. 구성요소 상호관계

### 6.1 의존성 흐름 (상위→하위)
```
UI(C12/C13/C14/C21)
   → App(C9 Hotkey, C10 Session, C4 Pipeline, C7 ModeMgr, C11 Config)
      → Core(C1 Audio, C2 STT, C3 LLM, C17 TextProc, C5 Injector,
             C6 Store, C8 Export, C18 ModelMgr)
Cross-cutting(C19 Secrets, C20 Logging) ← 모든 계층에서 사용
RemoteGateway(C15) → C10 → C4 (허브 파이프라인 재사용)
Packaging(C16)/Updater(C22) → 전체 산출물
```

### 6.2 대표 데이터 흐름 (단위 녹음)
```
C9(핫키) → C10(세션 생성) → C1(녹음+VAD) → C4:
   stage1 C2(STT) → C17(정규화/스니펫) → C6 저장 → (inject_stage=1이면 C5 주입)
   stage2 C3(교정) → C6 저장 → (inject_stage=2면 C5 주입)
   stage3 C3(리포트) → C6 저장
→ C13(작업대 표시) → C8(내보내기)
```

### 6.3 실시간 흐름
```
C1(스트림+VAD 세그먼트) → C4.stage1(C2) → C17 → 즉시 C5 주입
→ 종료 시 선택적 C3 교정 → C5 replacement(기존 텍스트 대체)
```

### 6.4 인터페이스 계약 (요약)
- **STTProvider**: `transcribe(audio) -> text`, `stream(chunks) -> segments`, `capabilities()`
- **LLMProvider**: `complete(system, text) -> text`, `stream(...)`, `capabilities()`
- **Injector**: `inject(text, method=auto|unicode|clipboard)`
- **TextProcessor**: `process(text, context) -> text`
- **Pipeline**: `run(audio, mode)`, `reprocess(session_id, from_stage)`
- **ModelManager**: `list()`, `ensure(model_id)`, `active()`

### 6.5 동시성/큐 정책
- UI 스레드는 블로킹 금지(Qt 이벤트 루프만).
- 오디오 스레드 + 추론 워커(faster-whisper는 GIL 회피 위해 별도 프로세스 고려).
- 결과 전달은 Qt Signal/Slot으로만(스레드 안전).
- 처리 중 핫키 재입력: 기본 "직전 세션 처리 완료까지 큐잉", 설정으로 "취소 후 새 세션" 선택 가능.

---

## 7. 데이터 모델 & 저장 위치

### 7.1 SQLite 스키마 (요약)
```
sessions(id, created_at, source, mode_id, audio_path, status)
artifacts(id, session_id, stage[1|2|3], text, provider, prompt_snapshot, created_at)
modes(id, name, target_stage, correction_prompt, report_prompt, inject_stage)
dictionaries(id, term, replacement, type[snippet|vocab])
settings(key, value)
```

### 7.2 사용자 데이터 경로 (Windows)
```
%APPDATA%\STT-AIO\
├─ app.db            # SQLite
├─ config.json       # 비민감 설정
├─ models\           # Whisper 모델 캐시
├─ audio\            # 오디오(보관 정책에 따라 자동 삭제)
└─ logs\             # 로그
```
- API 키 등 비밀정보는 위 파일이 아닌 **Windows 보안 저장소(DPAPI)** 에 저장.

---

## 8. 개발 단계(Phase) 로드맵

| Phase | 이름 | 목표 | 완료 기준(DoD) |
|-------|------|------|----------------|
| P0 | 기술 스파이크 | 최상위 리스크 검증 | ① 메모장 등 한글 정상 주입 0% 손실 ② faster-whisper 배치 STT 동작 ③ Ollama 연결 확인 ④ 실시간 스트리밍 지연 실측 |
| P1 | Windows MVP | 실사용 받아쓰기 | 핫키(PTT/토글)→단위녹음→로컬STT(1차)→커서주입, 트레이+오버레이 |
| P2 | 파이프라인+Provider | 가공·스위칭 | 로컬↔클라우드 전환, 2/3차 가공, 실시간 모드, 모드 시스템, 설정창, 텍스트 후처리 |
| P3 | 문서화+배포 | 산출·배포 | 작업대 재가공, txt/md/docx, 히스토리, 온보딩, 인스톨러, 로깅/진단 |
| P4 | 원격 위성(선택) | 폰 녹음 연동 | PWA 녹음→터널(QR/PIN)→허브 파이프라인 투입 |
| P5 | 안정화/업데이트 | 운영 품질 | 자동 업데이트, 성능 튜닝, NFR 목표 달성 |

각 Phase의 상세 작업·수용 기준·의존성은 `devplans/phases/*.md`에 작성.

### 8.1 Phase별 상세 개발 방향

#### P0. 기술 스파이크
목표는 제품을 만들기 전 가장 위험한 기술 가정을 빠르게 깨보는 것이다.

- **검증 대상**: 한글 주입, 마이크 녹음, faster-whisper 배치 STT, Ollama 연결, VAD 세그먼트 지연.
- **개발 방식**: 정식 UI 없이 작은 검증 스크립트/CLI로 진행한다. 이 단계의 코드는 버릴 수 있어야 한다.
- **필수 산출물**: 측정 결과 문서, 성공/실패 로그, 채택/보류 기술 목록, P1 구현 결정.
- **P1로 넘길 정보**: 권장 오디오 라이브러리, 주입 방식 우선순위, 최소 Whisper 모델, GPU/CPU 성능 기준.

#### P1. Windows MVP
목표는 "핫키를 누르고 말하면 현재 커서 위치에 한국어 텍스트가 들어간다"는 핵심 가치를 완성하는 것이다.

- **포함 기능**: 트레이 앱, 오버레이 상태 표시, PTT/토글 녹음, 단위 녹음, 로컬 STT 1차 변환, 커서 주입.
- **제외 기능**: LLM 교정, docx 출력, 모바일/웹 위성, 자동 업데이트.
- **필수 산출물**: 설치 없이 실행 가능한 개발 빌드, 기본 설정 파일, 최소 로그, 수동 테스트 체크리스트.
- **P2로 넘길 정보**: 실제 사용자 흐름에서 병목이 된 지점, Store 스키마 보완점, 주입 실패 앱 목록.

#### P2. 파이프라인 + Provider
목표는 단순 받아쓰기를 "선택형 3단계 가공 시스템"으로 확장하는 것이다.

- **포함 기능**: STT/LLM Provider 추상화, Ollama/OpenAI 호환 연동, 모드 시스템, 2차 교정, 3차 리포트, 실시간 1차 입력, 텍스트 후처리.
- **핵심 판단**: 실시간 경로와 LLM 경로를 분리한다. 실시간은 1차 입력을 기본으로 하고, 2/3차는 종료 후 재가공으로 처리한다.
- **필수 산출물**: Provider별 capabilities, 기본 모드 프리셋, Pipeline E2E 테스트, 설정 UI.
- **P3로 넘길 정보**: artifact 저장 구조 안정성, 사용자 편집/재가공 UX, 기본 프롬프트 품질.

#### P3. 문서화 + 배포
목표는 실사용자가 세션을 관리하고 산출물을 파일로 내보낼 수 있게 만드는 것이다.

- **포함 기능**: Workbench, 세션 히스토리, artifact 비교/편집, txt/md/docx 내보내기, Onboarding, 인스톨러, 진단 export.
- **핵심 판단**: 모델은 설치본에 기본 포함하지 않고, Onboarding/ModelManager에서 다운로드 또는 경로 지정을 유도한다.
- **필수 산출물**: Setup.exe 또는 포터블 빌드, 사용자 설정/데이터 경로 확정, 진단 패키지 포맷, QA 체크리스트.
- **P4로 넘길 정보**: 허브 파이프라인 안정성, 원격 업로드를 받을 SessionManager API, 보안 정책.

#### P4. 원격 위성
목표는 모바일/웹을 "녹음 전용 위성"으로 붙이는 것이다.

- **포함 기능**: FastAPI 수신 서버, PWA 녹음 UI, QR/PIN 페어링, Cloudflare Tunnel 연동, remote source 세션 생성.
- **제외 기능**: 모바일/웹에서 다른 앱으로 텍스트 주입, 모바일 네이티브 앱.
- **필수 산출물**: 모바일 브라우저 녹음 → Windows 허브 artifact 생성 E2E, 페어링 보안 검증, 업로드 제한 정책.
- **P5로 넘길 정보**: 네트워크 실패 패턴, 사용자 접속 UX, 터널 안정성.

#### P5. 안정화/업데이트
목표는 제품 운영 품질을 높이는 것이다.

- **포함 기능**: 성능 튜닝, 자동/반자동 업데이트, 코드사인 검토, 장기 회귀 테스트, 장애 진단 개선.
- **핵심 판단**: 자동 업데이트는 무결성 검증과 코드사인 전략이 준비된 뒤 단계적으로 활성화한다.
- **필수 산출물**: 릴리스 체크리스트, 성능 리포트, 업데이트 정책, 알려진 이슈 목록.

### 8.2 Phase 간 인수인계 기준
각 Phase가 다음 Phase로 넘어가려면 아래 정보를 반드시 남긴다.

| 인수인계 항목 | 설명 |
|---------------|------|
| 결정 기록 | 기술 선택 이유, 포기한 대안, 보류한 이슈 |
| 측정값 | 지연 시간, 메모리, STT 정확도, 주입 성공률 |
| API 계약 | 다음 Phase에서 의존할 함수/이벤트/데이터 구조 |
| 실패 사례 | 재현 조건, 로그 위치, 임시 회피책 |
| 사용자 영향 | UX 변경점, 설정 변경점, 문서화 필요 사항 |

---

## 9. 단계 × 구성요소 매트릭스

`● 주요 개발 · ◐ 부분/확장 · (빈칸) 해당 없음`

| 구성요소 \ Phase | P0 | P1 | P2 | P3 | P4 | P5 |
|------------------|----|----|----|----|----|----|
| C1 AudioCapture | ●(배치) | ● | ◐(스트림/VAD) | | | ◐ |
| C2 STTProvider | ●(로컬) | ● | ◐(클라우드/스트림) | | | ◐ |
| C3 LLMProvider | ◐(연결확인) | | ● | ◐ | | |
| C4 Pipeline | | ◐(1차) | ● | ◐(재가공) | ◐ | |
| C5 Injector | ●(검증) | ● | ◐ | | | |
| C6 Store | | ◐ | ● | ◐ | | |
| C7 ModeManager | | | ● | | | |
| C8 Exporter | | | | ● | | |
| C17 TextProcessor | | | ● | ◐ | | |
| C18 ModelManager | ◐ | ◐ | ◐ | ● | | |
| C9 HotkeyManager | | ● | ◐ | | | |
| C10 SessionManager | | ◐ | ● | | ◐ | |
| C11 Config | | ◐ | ● | | | |
| C19 Secrets/Security | | | ◐ | ● | ◐ | |
| C20 Logging/Diag | ◐ | ◐ | ◐ | ● | | ◐ |
| C12 UI Tray/Overlay | | ● | ◐ | | | |
| C13 UI Workbench | | | ◐ | ● | | |
| C14 UI Settings/Modes | | | ● | ◐ | | |
| C21 UI Onboarding | | | | ● | | |
| C15 RemoteGateway | | | | | ● | |
| C16 Packaging | | | ◐ | ● | ◐ | ◐ |
| C22 Updater | | | | | | ● |

### 9.1 구성요소 개발 권장 순서 (의존성 기반)
```
C6 Store → C11 Config → C1 Audio → C2 STT → C5 Injector → C9 Hotkey → C10 Session
→ C4 Pipeline → C7 Mode → C3 LLM → C17 TextProc → C14/C13 UI → C8 Export
→ C18 Model → C19 Secrets → C20 Logging → C21 Onboarding → C16 Packaging
→ C15 Remote → C22 Updater
```

---

## 10. 기술 스택

| 영역 | 선택 | 근거 |
|------|------|------|
| 언어 | Python 3.11+ | STT/LLM 생태계 |
| GUI | PySide6 | LGPL(상업 배포 자유) |
| STT(로컬) | faster-whisper(CTranslate2) | 경량·고속 표준 |
| STT(클라우드) | Groq/Deepgram/OpenAI | 저지연·스트리밍 |
| VAD | Silero VAD | 사실상 표준 |
| LLM(로컬) | Ollama | HTTP 연동 |
| LLM(클라우드) | OpenAI 호환 | Groq/OpenRouter 공용 |
| 주입 | Win32 SendInput(UNICODE)+Clipboard | 한글 안정성 |
| 저장 | SQLite | 로컬·트랜잭션 |
| 비밀정보 | Windows DPAPI | 평문 저장 방지 |
| 문서 | python-docx, Markdown | docx/md 출력 |
| 원격 | FastAPI+PWA+Cloudflare Tunnel | 무비용·자동 HTTPS |
| 배포 | PyInstaller/Nuitka+Inno Setup | exe·설치본 |
| CI | GitHub Actions(예정) | 빌드 자동화 |

### 10.1 주요 기술 선택 검증

| 영역 | 현재 선택 | 검증 결과 | 보류/대안 |
|------|-----------|-----------|-----------|
| Desktop UI | PySide6 | Windows 트레이/오버레이/설정 UI에 적합하고 LGPL이라 배포 리스크가 낮다. | Tauri/Rust는 배포 품질은 좋지만 AI Python 생태계 연동 비용이 크다. |
| 로컬 STT | faster-whisper | Python 기반, CTranslate2로 상대적으로 가볍고 GPU/CPU 선택이 가능하다. | whisper.cpp는 배포·CPU 친화 대안으로 P0에서 비교 가치가 있다. |
| VAD | Silero VAD | 실시간 세그먼트 감지의 검증된 선택이다. | WebRTC VAD는 가볍지만 한국어 발화 경계 품질 비교 필요. |
| 로컬 LLM | Ollama | 사용자가 모델을 쉽게 설치/교체할 수 있고 HTTP API가 단순하다. | LM Studio/llama.cpp server는 OpenAI 호환 Provider로 흡수 가능. |
| 클라우드 LLM | OpenAI 호환 API | OpenAI/Groq/OpenRouter 등 확장성이 좋다. | Anthropic 직접 API는 후순위 별도 Provider. |
| 커서 주입 | SendInput UNICODE + Clipboard | 한글 안정성과 범용성을 동시에 만족한다. | pynput 단일 방식은 한글 IME 리스크로 부적합. |
| 저장소 | SQLite | 로컬 단일 사용자 앱의 세션/산출물/설정 저장에 충분하다. | 파일 기반 JSON은 마이그레이션/조회가 약하다. |
| 원격 위성 | FastAPI + PWA + Tunnel | 모바일 앱 없이 HTTPS 마이크 권한과 QR 접속을 해결한다. | 중앙 중계 서버는 상용화 시 검토. |
| 배포 | PyInstaller/Nuitka + Inno Setup | Python 앱의 현실적인 Windows 배포 경로다. | MSIX는 서명/스토어 정책까지 고려할 때 후순위. |

### 10.2 기본 구현 원칙
- **동작하는 최소 경로를 먼저 만든다**: P1까지는 "단위 녹음 → 1차 STT → 주입" 이외 기능을 넣지 않는다.
- **Provider는 처음부터 인터페이스를 둔다**: 구현체가 하나뿐이어도 추상 계약을 먼저 만든다.
- **실시간과 배치를 같은 Pipeline에 억지로 합치지 않는다**: 공통 artifact 저장은 공유하되 입력 단위와 지연 정책은 분리한다.
- **사용자 텍스트는 민감 데이터로 본다**: 로그/진단/텔레메트리에 원문을 기본 포함하지 않는다.
- **한국어는 별도 테스트 기준을 둔다**: 영어 기준으로 통과해도 한글 조합/띄어쓰기/문장부호가 깨지면 실패로 본다.

---

## 11. 보안 & 프라이버시

- **API 키**: Windows DPAPI/Credential Manager에 저장, 로그/설정 파일에 평문 노출 금지.
- **오디오 보관 정책**: 기본 "처리 후 삭제" 옵션 + 보관 기간 설정. 위치는 `%APPDATA%\STT-AIO\audio`.
- **로컬 우선**: 기본 프라이버시 모드에서는 오디오/텍스트가 외부로 나가지 않음. 클라우드 사용 시 "전송 대상" 명시.
- **텔레메트리**: 기본 OFF, 옵트인. 크래시 리포트도 사용자 동의 기반.
- **원격 위성**: 페어링(PIN/QR) + 터널 HTTPS, 인증 없는 접근 차단.

---

## 12. 테스트 & QA 전략

- **단위 테스트**: 각 구성요소 인터페이스 계약 기준(특히 Provider mock).
- **한국어 정확도 회귀**: 고정 한국어 오디오 샘플셋 → WER 추적(모델·설정 변경 시).
- **주입 통합 테스트**: 메모장/브라우저/IDE 대상 한글·특수문자 손실 검증(P0 필수).
- **파이프라인 E2E**: 오디오 입력 → 1/2/3차 산출물 → 내보내기까지.
- **성능 테스트**: NFR(3절) 지연/리소스 목표 실측.
- **테스트 데이터**: `tests/fixtures/`에 짧은/긴/노이즈 포함 한국어 샘플.

---

## 13. 문서 체계 (앞으로 작성할 개별 문서)

모든 계획 문서는 본 README와 **동일 폴더(`devplans/initial/`)** 에 둔다.

```
devplans/initial/
├─ README.md                 # (본 문서) 마스터 계획
├─ C1-audio-capture.md        ├─ C12-ui-tray-overlay.md
├─ C2-stt-provider.md         ├─ C13-ui-workbench.md
├─ C3-llm-provider.md         ├─ C14-ui-settings-modes.md
├─ C4-pipeline.md             ├─ C15-remote-gateway.md
├─ C5-injector.md             ├─ C16-packaging.md
├─ C6-store.md                ├─ C17-text-processor.md
├─ C7-mode-manager.md         ├─ C18-model-manager.md
├─ C8-exporter.md             ├─ C19-secrets-security.md
├─ C9-hotkey-manager.md       ├─ C20-logging-diagnostics.md
├─ C10-session-manager.md     ├─ C21-ui-onboarding.md
├─ C11-config.md              └─ C22-updater.md
└─ (Phase 문서는 이후 별도 작성: P0~P5)
```

### 13.1 구성요소 문서 공통 템플릿
1. 목적/책임
2. 선택 근거와 대안 검토
3. 공개 인터페이스 계약
4. 입력/출력 데이터와 상태 전이
5. 의존 구성요소와 호출 관계
6. 내부 설계
7. 오류/폴백/재시도 정책
8. 성능 목표
9. 보안/프라이버시 고려사항
10. 테스트 항목
11. 관련 Phase와 구현 범위
12. 미결정 사항

### 13.2 Phase 문서 공통 템플릿
1. 목표/범위
2. 포함 구성요소
3. 선행 조건
4. 작업 목록(WBS)
5. 산출물
6. 수용 기준(DoD)
7. 측정/검증 방법
8. 다음 Phase 인수인계 항목
9. 리스크와 대응

---

## 14. 미결정 사항 (착수 전 확정 필요)
1. 기본 실행 환경 GPU 유무 → 실시간 로컬 STT 전략(모델 크기)
2. 기본값: 로컬(프라이버시) vs 클라우드(간편) — 첫 실행 경험 결정
3. 목표: 개인용 vs 배포/상용 → 코드사인, 위성 방식(터널 vs 중계서버), 업데이트 정책
4. 앱 브랜드/제품명 확정(현재 코드명 "STT-AIO")

---

## 15. 백로그 (범위 밖 / 후순위)
- 화자 분리(diarization)
- 실시간 번역/영어 변환
- 팀 기능·클라우드 동기화·공유 사전
- macOS/Linux 이식
- IDE 확장(예: Cursor/VS Code 연동)

---

## 16. 리스크 & 대응
| 리스크 | 영향 | 대응 |
|--------|------|------|
| 한글 IME 주입 깨짐 | 치명 | SendInput UNICODE 우선, P0 선검증 |
| 패키징 용량/GPU 이슈 | 중 | 모델 최초실행 다운로드, 클라우드 기본 |
| 실시간 2차 지연 | 중 | 실시간은 1차만 즉시, 2/3차 종료 후 |
| API 키 유출 | 높음 | DPAPI 저장, 로그 마스킹 |
| 미서명 SmartScreen | 중 | 초기 감수, 확대 시 코드사인 |
| 위성 HTTPS/네트워크 | 중 | Cloudflare Tunnel(자동 HTTPS)+페어링 |
| 처리 중 재입력 충돌 | 낮 | 큐잉 정책(6.5절) |

---

## 17. 용어집 (Glossary)
- **STT**: Speech-to-Text, 음성→텍스트 변환
- **1/2/3차 가공**: 원문 STT / LLM 교정 / 리포트 생성
- **모드(Mode)**: 목표 단계 + 프롬프트 + 주입 단계를 묶은 프리셋
- **주입(Injection)**: 커서 위치에 텍스트 자동 입력
- **PTT**: Push-to-Talk, 누르는 동안 녹음
- **위성(Satellite)**: 녹음만 담당하는 모바일/웹 클라이언트
- **허브(Hub)**: 모든 처리를 담당하는 Windows 앱
- **WER**: Word Error Rate, STT 정확도 지표

---

## 18. 다음 액션
1. 14절 미결정 4가지 확정
2. `phases/P0-spike.md` 상세화 → 스파이크 착수
3. 이후 `components/*.md` 를 9.1 권장 순서대로 순차 작성
