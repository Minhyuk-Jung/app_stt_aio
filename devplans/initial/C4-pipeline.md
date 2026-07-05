# C4. Pipeline 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C4 |
| 이름 | Pipeline (가공 오케스트레이터) |
| 계층 | Core Engine |
| 관련 Phase | P1(1차), P2(2/3차·모드), P3(재가공), P4(원격 소스) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
오디오/텍스트를 입력받아 **1→2→3차 가공을 모드 설정에 따라 라우팅**하고, 각 단계 산출물을 저장·방출한다. UI/원격/CLI가 공유하는 단일 처리 흐름.

- 모드(target_stage, inject_stage)에 따른 단계 실행 제어.
- 각 stage 실행 전후 Store 저장 및 이벤트 발행.
- 특정 단계부터 재가공(reprocess).
- 실시간 경로와 배치 경로의 처리 정책 분리.

**책임이 아닌 것**: STT/LLM 실제 추론(C2/C3), 주입(C5), 프롬프트 보관(C7), 세션 수명주기(C10).

---

## 2. 선택 근거와 대안 검토
- **독립 오케스트레이터 분리**: UI·RemoteGateway·테스트가 동일 처리 로직을 재사용해야 하므로 파이프라인을 별도 구성요소로 둔다.
- **stage 저장을 파이프라인이 책임**: 중간 산출물 각각 보존(제품 차별점). stage별 artifact를 남겨 재가공/내보내기의 기반.
- **inject_stage와 target_stage 분리**: "생성 단계"와 "주입 단계"는 다르다(예: 회의록은 3차 생성하되 주입 안 함).

---

## 3. 공개 인터페이스 계약
- `run(input: PipelineInput, mode: Mode) -> PipelineRun`: 신규 실행.
- `reprocess(session_id, from_stage, mode?) -> PipelineRun`: 기존 세션의 특정 단계부터 재실행.
- 이벤트: `on_stage_started(stage)`, `on_stage_completed(stage, artifact)`, `on_inject_requested(artifact)`, `on_pipeline_error(stage, error)`, `on_pipeline_finished(run)`.

`PipelineInput` = { source[batch|realtime|remote], audio?: AudioBuffer, seed_text?: str, session_id? }.
`PipelineRun` = { session_id, artifacts[by stage], status }.

---

## 4. 입력/출력 데이터와 상태 전이
- 입력: 오디오(신규) 또는 기존 artifact(재가공).
- 출력: stage별 artifact(C6 저장) + 주입 요청 이벤트.
- 단계 상태: `pending → running(stage) → saved(stage) → next/finished`.
- 실패 시: 해당 stage `error`, 직전 stage 산출물은 보존, 파이프라인 중단(부분 성공).

### 실행 규칙(모드 기반)
```
stage1(STT) 항상 실행(신규 오디오 입력 시)
 if mode.target_stage >= 2: stage2(LLM 교정)
 if mode.target_stage >= 3: stage3(LLM 리포트)
각 stage 완료 후: stage == mode.inject_stage 이면 on_inject_requested 방출
```

---

## 5. 의존 구성요소와 호출 관계
- **호출자**: C10 SessionManager(신규 실행/재가공), C13 Workbench(재가공), C15 RemoteGateway(원격 입력).
- **의존**: C2 STT, C3 LLM, C6 Store, C7 ModeManager(프롬프트), C17 TextProcessor(1차 후처리).
- **하위 방출**: 주입 요청 → C10/C5, 진행 이벤트 → C12 UI.

---

## 6. 내부 설계
### 6.1 구조
- `pipeline.py`: 실행 엔진(단계 루프, 이벤트).
- `stages.py`: stage1/2/3 각 실행 단위(입력→provider 호출→후처리→저장).
- `queue.py`: 처리 큐(동시 실행 직렬화, C10 정책 연계).
- `events.py`: 이벤트 정의/디스패치.

### 6.2 실행 절차(신규, 단위 녹음)
1. session 생성/획득(C10) → status=processing.
2. stage1: C2.transcribe → C17.process(정규화/사전/스니펫) → C6 저장(stage1) → inject 조건 확인.
3. target_stage≥2: C7에서 correction_prompt 획득 → C3.complete → C6 저장(stage2) → inject 조건.
4. target_stage≥3: C7에서 report_prompt 획득 → C3.complete → C6 저장(stage3).
5. `on_pipeline_finished`.

### 6.3 실시간 경로
- C1의 세그먼트마다 stage1만 즉시 실행 → 후처리 → 즉시 주입 요청.
- 2/3차는 실시간에 끼우지 않음(기본). 녹음 종료 시 사용자가 선택하면 `reprocess(from_stage=2)`로 교체(replacement) 흐름.

### 6.4 재가공(reprocess)
- from_stage 기준으로 이후 단계만 재실행.
- 사용자가 1차 텍스트를 수정한 경우, 수정본을 입력으로 stage2부터 실행.
- 재가공 결과는 기존 artifact를 갱신할지 새 버전으로 남길지 → 기본 "갱신 + 변경 이력 최소 보존"(C6와 협의, 미결정).

### 6.5 동시성/큐
- 한 번에 하나의 파이프라인만 실행(직렬). 처리 중 새 입력은 C10 정책(기본 큐잉)에 따름.
- 취소 요청 시 현재 stage 경계에서 안전 중단.

---

## 7. 오류/폴백/재시도 정책
- stage 실패 시 이후 단계 중단, 직전 산출물 보존, `on_pipeline_error` 방출.
- STT 실패: 세션 실패 처리(1차 없음).
- LLM 실패: 1차(또는 2차) 산출물 유지 + 사용자 알림, 주입은 직전 성공 단계 기준으로 진행할지 정책화(기본: inject_stage 미달 시 주입 안 함 + 알림).
- 재시도는 각 provider가 담당, 파이프라인은 최종 결과만 처리.

---

## 8. 성능 목표
- 오케스트레이션 오버헤드(provider 시간 제외)는 무시할 수준.
- 이벤트 방출은 비동기로 UI 블로킹 없음.
- 실시간 세그먼트 처리 지연은 C1+C2 합산 목표(1초) 내 유지.

---

## 9. 보안/프라이버시 고려사항
- prompt_snapshot 저장 시 민감 정보 포함 여부 점검(기본 프롬프트는 안전).
- 원문 텍스트는 Store 정책을 따름, 로그에는 미기록.

---

## 10. 테스트 항목
- 단위: 모드별 stage 실행 조합(1만/2까지/3까지), inject 조건, 재가공 범위.
- 통합: mock provider로 전체 흐름 + 이벤트 순서 검증.
- 엣지: stage2 실패 후 상태, 취소, 처리 중 재입력 큐잉, 실시간→종료 후 교체.
- E2E: 오디오→3차→내보내기(C8 연계).

---

## 11. 관련 Phase와 구현 범위
- **P1**: stage1 전용 최소 파이프라인(오디오→STT→후처리→주입).
- **P2**: 2/3차, 모드 라우팅, 실시간 경로, 큐.
- **P3**: 재가공, Workbench 연계.
- **P4**: 원격 소스 입력 수용.

---

## 12. 미결정 사항
- 재가공 결과의 버전 관리(갱신 vs 이력 보존) 세부.
- inject_stage 미달 시 부분 주입 허용 여부.
- 실시간 replacement의 텍스트 대체 범위 산정 방식.
