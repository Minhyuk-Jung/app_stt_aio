# C10. SessionManager 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C10 |
| 이름 | SessionManager (세션 수명주기) |
| 계층 | Application |
| 관련 Phase | P1(최소), P2(핵심), P4(원격) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
녹음 한 단위(세션)의 수명주기를 관리하고, 입력 소스와 파이프라인/주입을 조율한다.

- 세션 생성/상태전이/취소/완료.
- 입력 소스 구분: batch(단위 녹음), realtime, remote.
- 트리거(C9)→캡처(C1)→파이프라인(C4)→주입(C5) 조율.
- 처리 중 재입력 큐잉 정책 관리.

**책임이 아닌 것**: 실제 추론(C2/C3), 저장 스키마(C6), UI 표시(C12).

---

## 2. 선택 근거와 대안 검토
- **세션 개념 분리**: batch/realtime/remote를 하나의 "세션"으로 통일해야 파이프라인/저장/UI가 일관됨.
- **오케스트레이션 계층**: 여러 Core 구성요소를 잇는 조율은 UI가 아니라 Application 계층에 둔다(UI 재사용/테스트 용이).

---

## 3. 공개 인터페이스 계약
- `begin(source, mode) -> session_id`.
- `stop(session_id)` / `cancel(session_id)`.
- `submit_remote(audio, mode) -> session_id`: 원격 입력 진입.
- 이벤트: `on_session_state(session_id, state)`, `on_inject(session_id, artifact)`.

상태(state): recording, processing, done, error, canceled.

---

## 4. 입력/출력 데이터와 상태 전이
```
begin → recording →(stop) processing →(pipeline done) done
recording →(cancel) canceled
processing →(pipeline error) error
```
- realtime: recording 동안 세그먼트별 처리·주입 병행.
- remote: recording 단계 없이 processing으로 진입.

---

## 5. 의존 구성요소와 호출 관계
- **호출자**: C9 Hotkey(트리거), C12 UI(수동 제어), C15 RemoteGateway(원격 제출), C13 Workbench(재가공 요청 전달).
- **의존**: C1 Audio, C4 Pipeline, C5 Injector, C6 Store, C7 Mode(현재 모드), C11 Config(큐 정책), C20 Logging.

---

## 6. 내부 설계
### 6.1 구조
- `session_manager.py`: 수명주기/상태 머신.
- `orchestration.py`: 캡처↔파이프라인↔주입 연결.
- `queue_policy.py`: 처리 중 재입력 정책(큐잉/취소/무시).
- `injection_bridge.py`: 파이프라인 inject 이벤트 → C5 호출(직전 주입 길이 추적).

### 6.2 배치 절차
1. `begin(batch)` → 세션 생성(C6, status=recording) → C1.start_batch.
2. `stop` → C1.stop_batch → C4.run(audio, mode) 처리(status=processing).
3. 파이프라인 inject 이벤트 → C5.inject.
4. 완료 → status=done, 이벤트 방출.

### 6.3 실시간 절차
1. `begin(realtime)` → C1.start_stream(on_segment).
2. 세그먼트마다 C4 stage1 → inject(직전 길이 추적, replacement 준비).
3. `stop` → 스트림 종료 → 선택 시 2/3차 reprocess로 교체.

### 6.4 큐 정책
- 기본: 처리 중 새 begin 요청은 큐잉(순차 처리).
- 옵션: 취소 후 새 세션 / 무시.
- 정책은 C11 설정.

---

## 7. 오류/폴백/재시도 정책
- 캡처 오류: 세션 error, 사용자 알림.
- 파이프라인 부분 실패: 성공 단계까지 저장, inject는 정책에 따름.
- 취소: 진행 리소스 정리(버퍼 폐기), 부분 산출물 저장 여부 정책(기본 미저장).

---

## 8. 성능 목표
- 트리거→녹음 시작 지연 최소(<50ms 체감).
- 상태 이벤트는 UI 논블로킹.

---

## 9. 보안/프라이버시 고려사항
- 오디오 보관은 C11 정책(기본 처리 후 삭제) 준수.
- 세션 메타/텍스트 로그 최소화.

---

## 10. 테스트 항목
- 단위: 상태 전이, 큐 정책, 소스별 분기(mock C1/C4/C5).
- 통합: 배치/실시간 전체 흐름, 취소, 재입력 큐잉.
- 엣지: stop 없이 앱 종료, 처리 중 취소, 원격+로컬 동시 요청.

---

## 11. 관련 Phase와 구현 범위
- **P1**: 배치 세션(begin/stop) + 주입 연결(최소).
- **P2**: 실시간 세션, 큐 정책, 상태 이벤트 정교화.
- **P4**: remote 소스 수용.

---

## 12. 미결정 사항
- 취소 시 부분 산출물 저장 여부.
- 기본 큐 정책 확정(큐잉 권장).
- 실시간 replacement를 SessionManager가 어디까지 책임질지(C5와 경계).
