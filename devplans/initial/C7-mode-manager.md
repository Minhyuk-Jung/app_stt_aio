# C7. ModeManager 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C7 |
| 이름 | ModeManager (모드/프롬프트 프리셋) |
| 계층 | Core Engine |
| 관련 Phase | P2(핵심) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
"모드"(가공 프리셋)를 관리한다. 모드는 **어디까지 생성하고(target_stage), 어디를 주입하며(inject_stage), 어떤 프롬프트로 가공할지**를 묶은 단위이며, 이 제품 UX의 핵심.

- 기본 모드 seed 제공 및 사용자 정의 모드 CRUD.
- Pipeline에 stage별 프롬프트/파라미터 공급.
- Provider override(모드별 STT/LLM 지정) 지원.

**책임이 아닌 것**: 실제 LLM 호출(C3), 단계 실행(C4), 저장 매체(C6).

---

## 2. 선택 근거와 대안 검토
- **모드 = 프롬프트 프리셋 개념**: Superwhisper/Kalam의 custom mode를 벤치마크. 사용자가 용도별(받아쓰기/교정/회의록/보고서)로 전환하는 것이 자연스럽다.
- **target/inject 분리**: 유연한 조합(생성만 하고 주입 안 함 등)을 표현하기 위함.
- **프롬프트를 DB에 저장**: 사용자가 편집·추가할 수 있어야 하므로 코드 상수가 아닌 데이터로 관리.

---

## 3. 공개 인터페이스 계약
- `list_modes() -> [Mode]`.
- `get_mode(id) -> Mode`.
- `create/update/delete_mode(...)`.
- `get_prompt(mode, stage) -> PromptSpec`: Pipeline이 stage별 프롬프트 획득.
- `seed_defaults()`: 최초 기본 모드 생성(멱등).

`Mode` = { id, name, target_stage(1..3), inject_stage(0..3), correction_prompt, report_prompt, stt_provider?, llm_provider?, params?, is_default }.
`PromptSpec` = { system_prompt, params }.

`inject_stage=0`은 "주입 안 함".

---

## 4. 입력/출력 데이터와 상태 전이
- 입력: 사용자 편집(UI) 또는 기본 seed.
- 출력: Pipeline/UI가 소비하는 Mode 객체.
- 상태 전이 없음(데이터 관리). 변경은 즉시 반영.

---

## 5. 의존 구성요소와 호출 관계
- **호출자**: C4 Pipeline(프롬프트 획득), C14 설정/모드 UI(CRUD), C12 오버레이(빠른 모드 전환).
- **의존**: C6 Store(ModeRepo).

---

## 6. 내부 설계
### 6.1 구조
- `mode_manager.py`: CRUD + 프롬프트 제공 로직.
- `defaults.py`: 기본 모드 정의(seed 데이터).
- `validation.py`: target/inject 정합성 검증.

### 6.2 기본 모드(seed 예)
| 이름 | target | inject | 설명 |
|------|--------|--------|------|
| 빠른 받아쓰기 | 1 | 1 | 원문 즉시 주입 |
| 문장 다듬기 | 2 | 2 | 교정본 주입 |
| 회의록 | 3 | 0 | 3차 생성, 주입 안 함(작업대에서 내보내기) |
| 보고서 | 3 | 0 | 보고서 양식 생성 |

- 기본 모드도 편집 가능하되 "기본값 복원" 제공.

### 6.3 검증 규칙
- inject_stage ≤ target_stage(단, 0 허용).
- report_prompt는 target_stage=3일 때만 의미.
- 프롬프트 공란 방지(기본값 대체).

### 6.4 프롬프트 관리
- 한국어 교정/리포트 기본 프롬프트를 품질 튜닝 대상으로 관리(P2~P3).
- 프롬프트에는 사용자 입력 텍스트가 들어갈 자리 표시(placeholder) 규칙 정의.

---

## 7. 오류/폴백/재시도 정책
- 잘못된 모드 참조 시 기본 모드로 폴백 + 경고.
- 프롬프트 누락 시 내장 기본 프롬프트 사용.

---

## 8. 성능 목표
- 조회/전환 즉시(캐시 가능). 무거운 연산 없음.

---

## 9. 보안/프라이버시 고려사항
- 프롬프트에 민감 정보가 저장될 수 있으므로 진단 export 시 포함 여부를 사용자에게 고지.

---

## 10. 테스트 항목
- 단위: CRUD, 검증 규칙, seed 멱등, 프롬프트 획득.
- 통합: Pipeline이 모드별로 올바른 stage/프롬프트 사용.
- 엣지: inject>target, 프롬프트 공란, 기본 모드 삭제 시도.

---

## 11. 관련 Phase와 구현 범위
- **P2**: 전체 모드 시스템 구현(seed + CRUD + Pipeline 연동).
- **P3**: 리포트 프롬프트 품질 개선, 사용자 프리셋 UX.

---

## 12. 미결정 사항
- 기본 모드 삭제 허용 여부(권장: 비활성만).
- 프롬프트 placeholder 문법.
- 모드별 provider override 노출 범위(초기엔 숨김 가능).
