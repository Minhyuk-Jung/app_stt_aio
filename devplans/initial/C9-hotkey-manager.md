# C9. HotkeyManager 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C9 |
| 이름 | HotkeyManager (전역 핫키) |
| 계층 | Application |
| 관련 Phase | P1(핵심), P2(확장) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
전역 단축키로 녹음/취소/자동전송 등의 동작을 트리거한다. Windows 어디서나 동작.

- PTT(누르는 동안 녹음)와 Toggle(눌러서 시작/정지) 모드.
- 녹음 시작/정지, 취소(Esc), 자동 전송(Enter) 트리거.
- 핫키 충돌 감지 및 사용자 재설정.

**책임이 아닌 것**: 실제 녹음(C1), 세션 관리(C10), 주입(C5).

---

## 2. 선택 근거와 대안 검토
- **전역 핫키는 핵심 UX**: Win+H 벤치마크. PTT/Toggle 둘 다 지원이 표준.
- **구현 방식**: Windows 전역 훅/RegisterHotKey 또는 검증된 라이브러리. 특수키(CapsLock, ScrollLock, Pause 등) 지원 여부를 P1에서 확인.
- **키 반복 이벤트 처리**: 키 홀드 시 반복 down 이벤트를 debounce.

---

## 3. 공개 인터페이스 계약
- `register(binding: HotkeyBinding)` / `unregister(id)`.
- `set_mode(ptt|toggle)`.
- 이벤트: `on_record_start`, `on_record_stop`, `on_cancel`, `on_auto_send`, `on_conflict(binding)`.
- `test_binding(keys) -> bool`: 설정 UI 충돌 확인.

`HotkeyBinding` = { id, keys, action[record|cancel|auto_send], mode }.

---

## 4. 입력/출력 데이터와 상태 전이
- 입력: 전역 키 이벤트.
- 출력: 의미 있는 액션 이벤트(상위로).
- 상태(PTT): `idle →(keydown) recording →(keyup) stopped→idle`.
- 상태(Toggle): `idle →(press) recording →(press) idle`.
- 취소는 어느 상태에서든 우선 처리.

---

## 5. 의존 구성요소와 호출 관계
- **호출자/구독자**: C10 SessionManager(녹음 시작/정지 수신).
- **의존**: Win32 훅/핫키 API, C11 Config(바인딩 저장), C20 Logging.
- **협조**: C5 Injector(자동전송 Enter는 주입 옵션과 연동).

---

## 6. 내부 설계
### 6.1 구조
- `hotkey_manager.py`: 등록/해제/이벤트 디스패치.
- `backend_win.py`: Windows 훅/핫키 구현.
- `debounce.py`: 키 반복/노이즈 제거.
- `conflict.py`: 시스템/타앱 충돌 감지 로직.

### 6.2 동작 절차(PTT)
1. 지정 키 down 감지 → debounce 통과 → `on_record_start`.
2. 키 up 감지 → `on_record_stop`.
3. 취소키(Esc)는 즉시 `on_cancel`(녹음/처리 취소).

### 6.3 자동 전송
- 특정 키 조합(예: Alt로 종료)일 때 `on_auto_send`로 구분 → 주입 후 Enter.

### 6.4 충돌 처리
- 등록 실패(이미 점유) 시 `on_conflict` → 사용자에게 재설정 요청.

---

## 7. 오류/폴백/재시도 정책
- 등록 실패: 대체 기본키 제안 + 설정 유도.
- 훅 비정상: 재등록 시도, 실패 시 알림.
- 관리자 권한 창에서 입력 제약은 C5와 함께 문서화(핫키는 대개 동작하나 주입이 막힐 수 있음).

---

## 8. 성능 목표
- 키 입력→이벤트 지연 무시 수준(<10ms 체감).
- 유휴 시 CPU 부담 없음.

---

## 9. 보안/프라이버시 고려사항
- 전역 키 후킹은 오해 소지가 있으므로 **키 로깅을 하지 않음**을 원칙화(지정 바인딩만 감지, 로그에 일반 키 입력 미기록).

---

## 10. 테스트 항목
- 단위: debounce, PTT/Toggle 상태 전이, 충돌 감지(mock).
- 통합: 실제 등록 후 다양한 앱 위에서 트리거.
- 엣지: 키 홀드 반복, 빠른 연타, 취소 우선순위, 등록 실패.

---

## 11. 관련 Phase와 구현 범위
- **P1**: PTT/Toggle + 녹음 시작/정지 + 취소.
- **P2**: 자동 전송, 바인딩 커스터마이즈 UI 연동, 충돌 감지 고도화.

---

## 12. 미결정 사항
- 기본 핫키 조합.
- 마우스 버튼(Mouse4/5) 지원 여부(벤치마크 사례 있음).
- 자동전송 트리거 방식(별도 키 vs 옵션).
