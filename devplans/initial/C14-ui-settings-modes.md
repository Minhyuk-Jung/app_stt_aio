# C14. UI-Settings/Modes 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C14 |
| 이름 | UI-Settings/Modes (설정·모드 관리) |
| 계층 | UI (PySide6) |
| 관련 Phase | P2(핵심), P3(확장) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
Provider/모델/API 키/마이크/핫키/프라이버시 설정과 모드(프롬프트 프리셋) 관리 UI를 제공한다.

- Provider 선택 + 연결 테스트 + 모델 목록 조회.
- API 키 입력(C19 위임) 및 상태 표시.
- 마이크 장치/핫키/보관 정책 등 설정 편집.
- 모드 CRUD 및 프롬프트 편집.

**책임이 아닌 것**: 설정 저장 로직(C11), 비밀 저장(C19), 실제 연결(C2/C3).

---

## 2. 선택 근거와 대안 검토
- **별도 설정 화면 필요**: Provider/키/모드 복잡도가 높아 오버레이로 불가.
- **연결 테스트 내장**: 실패 사유를 사용자 언어로 즉시 피드백(벤치마크 UX).

---

## 3. 공개 인터페이스 계약
- 발신: `save_setting(section,key,value)`, `set_api_key(name,value)`, `test_connection(provider)`, `refresh_models(provider)`, `mode CRUD`, `download_model(model_id)`.
- 구독: `on_connection_result`, `on_model_list`, `on_download_progress`.

---

## 4. 입력/출력 데이터와 상태 전이
- 입력: 현재 설정(C11), 모델/모드 데이터.
- 출력: 설정/키/모드 변경.
- 탭 상태: General / STT / LLM / Hotkey / Privacy / Modes / Models.

---

## 5. 의존 구성요소와 호출 관계
- **의존**: C11 Config, C19 Secrets, C2/C3(연결 테스트/모델 목록), C18 ModelManager(다운로드), C7 ModeManager(모드 CRUD).

---

## 6. 내부 설계
### 6.1 구조
- `settings_window.py`: 탭 컨테이너.
- `page_stt.py` / `page_llm.py`: provider/키/모델/연결 테스트.
- `page_hotkey.py`: 바인딩 편집 + 충돌 확인(C9).
- `page_privacy.py`: 보관/텔레메트리.
- `page_modes.py`: 모드 목록/편집(프롬프트, target/inject).
- `page_models.py`: 모델 목록/다운로드/활성 선택.

### 6.2 동작 원칙
- 연결 테스트/모델 조회/다운로드는 워커에서 실행, 결과를 신호로 표시.
- 키 입력은 즉시 C19 저장, UI엔 마스킹/상태만.
- 검증 실패 항목은 인라인 오류 표시.

### 6.3 연결 테스트 흐름
1. provider/키/base_url 입력.
2. `test_connection` → 성공/실패 사유 표시.
3. 성공 시 `refresh_models`로 모델 목록 채움.

---

## 7. 오류/폴백/재시도 정책
- 연결 실패: 원인별 메시지(인증/네트워크/URL).
- 모델 다운로드 실패: 재시도 버튼(C18 재개).
- 저장 실패: 이전 값 유지 + 경고.

---

## 8. 성능 목표
- 화면 전환 즉시. 네트워크 작업은 비동기 + 진행 표시.

---

## 9. 보안/프라이버시 고려사항
- API 키는 화면에 평문 재노출 금지(마스킹/붙여넣기 입력).
- 프라이버시 탭에서 데이터 전송/보관을 명확히 설명.

---

## 10. 테스트 항목
- 단위: 폼 검증, 액션 발신, 마스킹 표시.
- 통합: 연결 테스트→모델 목록, 키 저장→provider 사용, 모드 편집→Pipeline 반영.
- 엣지: 잘못된 키/URL, 오프라인, 대량 모드.

---

## 11. 관련 Phase와 구현 범위
- **P2**: STT/LLM/Hotkey/Modes 핵심 설정 + 연결 테스트.
- **P3**: Models/Privacy 탭, 다운로드 UI 완성.

---

## 12. 미결정 사항
- 모드 편집 고급 옵션(provider override) 노출 범위.
- 설정 검색 기능 여부.
- 프롬프트 편집기 수준(단순 텍스트 vs 도움말/변수 안내).
