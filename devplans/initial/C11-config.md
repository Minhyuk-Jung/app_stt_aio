# C11. Config 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C11 |
| 이름 | Config (설정 관리) |
| 계층 | Application |
| 관련 Phase | P1(최소), P2(핵심) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
앱 설정을 타입 안전하게 관리하고 영속화한다. 비민감 설정만 다루며 민감정보는 C19에 위임.

- 설정 스키마/기본값/검증/마이그레이션.
- 마이크 장치, 활성 provider/모델, 핫키, 큐 정책, 보관 정책 등.
- 사용자 데이터 경로 규칙 제공.

**책임이 아닌 것**: 비밀정보(C19), 저장 매체 자체(C6), UI(C14).

---

## 2. 선택 근거와 대안 검토
- **Store와 분리된 도메인 계층**: UI가 직접 DB key를 다루면 변경 영향 범위가 커짐. 타입/기본값/검증을 캡슐화.
- **저장 위치**: 구조적 설정은 C6(settings 테이블) 사용, 단순 부트스트랩 값은 `config.json` 병행 가능. 일관성 위해 기본은 settings 테이블.
- 대안(순수 파일 설정): 검증/조회 약함 → 도메인 계층으로 보완.

---

## 3. 공개 인터페이스 계약
- `get(key) -> typed value` / `set(key, value)`.
- `get_section(name) -> dict`(예: audio, stt, llm, hotkey, privacy).
- `on_change(key, callback)`: 설정 변경 구독.
- `reset(key|section)`: 기본값 복원.
- `paths() -> AppPaths`: 데이터/모델/오디오/로그 경로.

---

## 4. 입력/출력 데이터와 상태 전이
- 입력: UI/온보딩의 설정 변경.
- 출력: 각 구성요소가 읽는 유효 설정값.
- 변경 즉시 반영 + 구독자 통지. 무거운 상태전이 없음.

### 주요 설정 섹션(초기)
```
audio: device_id, vad_threshold, min_speech_ms, hangover_ms, max_segment_ms
stt: provider, model, language, fallback_to_local
llm: provider, model, base_url
hotkey: bindings, mode(ptt|toggle), auto_send
privacy: keep_audio, audio_retention_days, telemetry(false)
inject: default_method, length_threshold, press_enter
session: queue_policy
export: default_dir, filename_pattern
```

---

## 5. 의존 구성요소와 호출 관계
- **호출자**: 사실상 모든 구성요소가 읽기, C14 설정 UI가 쓰기.
- **의존**: C6 Store(settings), C19 참조(민감 키는 위임), C20 Logging.

---

## 6. 내부 설계
### 6.1 구조
- `config.py`: 접근 API + 변경 통지.
- `schema.py`: 키/타입/기본값/검증 규칙 정의.
- `paths.py`: `%APPDATA%\STT-AIO\...` 경로 규칙.
- `migration.py`: 설정 스키마 버전 관리.

### 6.2 절차
1. 앱 시작 시 설정 로드(없으면 기본값 생성).
2. 스키마 검증(범위/타입) → 위반 시 기본값 대체 + 경고 로그.
3. 변경 시 검증 후 저장 + 구독자 통지.

### 6.3 경로 규칙
- 기본 루트 `%APPDATA%\STT-AIO`, 하위 models/audio/logs/app.db.
- 포터블 모드(선택): 실행 폴더 기준 경로(백로그).

---

## 7. 오류/폴백/재시도 정책
- 손상 설정: 기본값으로 복구 + 백업 보관.
- 알 수 없는 키: 무시 + 로그(하위 호환).

---

## 8. 성능 목표
- 읽기는 캐시로 즉시. 쓰기는 소량이라 부담 없음.

---

## 9. 보안/프라이버시 고려사항
- 민감정보(API 키 등)는 저장 금지 → C19.
- telemetry 기본 false.

---

## 10. 테스트 항목
- 단위: get/set/검증/기본값 복원, 변경 통지, 마이그레이션.
- 통합: 설정 변경이 각 구성요소 동작에 반영.
- 엣지: 손상 파일, 범위 초과 값, 알 수 없는 키.

---

## 11. 관련 Phase와 구현 범위
- **P1**: 최소 설정(오디오 장치, 활성 모델, 핫키) + 경로 규칙.
- **P2**: 전체 섹션, 변경 통지, UI 연동, 마이그레이션.

---

## 12. 미결정 사항
- config.json 병행 여부(기본: settings 테이블 단일화).
- 포터블 모드 지원 시점.
- 설정 변경의 즉시 적용 vs 재시작 필요 항목 구분.
