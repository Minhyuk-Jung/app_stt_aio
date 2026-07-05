# C19. Secrets/Security 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C19 |
| 이름 | Secrets/Security (비밀정보·보안) |
| 계층 | Application (교차 관심사) |
| 관련 Phase | P2(핵심), P3/P4(확장) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
API 키 등 민감 정보를 안전하게 저장/조회하고, 로그 마스킹·오디오 보관 정책 검증 등 보안 관심사를 담당한다.

- 비밀정보 저장/조회/삭제(Windows DPAPI/Credential Manager).
- 로그 마스킹 유틸(키/토큰/원문 보호).
- 오디오/텍스트 보관 정책 검증·집행 협조.

**책임이 아닌 것**: 일반 설정(C11), 로깅 자체(C20, 단 마스킹 규칙 제공), 네트워크 호출(각 provider).

---

## 2. 선택 근거와 대안 검토
- **클라우드 provider 지원 시 필수**: 평문 저장은 위험. Windows DPAPI/Credential Manager로 OS 보안 저장소 사용.
- **평문 fallback 금지**: 개발 편의라도 평문 저장을 만들지 않는다(원칙). 테스트는 mock secret store.
- 대안(설정 파일에 키 저장): 유출 위험으로 배제.

---

## 3. 공개 인터페이스 계약
- `set_secret(name, value)` / `get_secret(name) -> value?` / `delete_secret(name)`.
- `has_secret(name) -> bool`.
- `mask(text) -> text`: 로그용 마스킹(키/토큰 패턴 치환).
- `validate_retention(policy) -> bool`: 보관 정책 유효성.

secret name 예: `stt.openai.api_key`, `llm.groq.api_key`, `remote.pairing_secret`.

---

## 4. 입력/출력 데이터와 상태 전이
- 입력: 사용자 입력 키, 로그 문자열.
- 출력: 보안 저장소 항목, 마스킹된 문자열.
- 무상태 서비스(저장소는 OS).

---

## 5. 의존 구성요소와 호출 관계
- **호출자**: C2 STT/C3 LLM(키 조회), C14 설정 UI(키 입력/삭제), C15 Remote(페어링 시크릿), C20 Logging(마스킹 규칙).
- **의존**: Windows DPAPI/Credential Manager API.

---

## 6. 내부 설계
### 6.1 구조
- `secrets.py`: 저장/조회 추상 + Windows 구현.
- `backend_win.py`: DPAPI 또는 Credential Manager 연동.
- `masking.py`: 민감 패턴 마스킹 규칙.
- `retention.py`: 오디오/텍스트 보관 정책 검증 로직.
- `mock_store.py`: 테스트용 인메모리(비영속).

### 6.2 저장 절차
1. 키 이름 정규화(네임스페이스 규칙).
2. 값 암호화 저장(DPAPI: 사용자 계정 범위).
3. 조회 시 복호화, 실패 시 없음 처리.

### 6.3 마스킹 규칙
- 알려진 키 이름/토큰 패턴을 `****`로 치환.
- 로그 출력 경로는 반드시 mask 경유(C20와 계약).

---

## 7. 오류/폴백/재시도 정책
- 저장소 접근 실패: 명확한 오류(키 저장 불가) + 재시도 안내. 평문 저장으로 폴백하지 않음.
- 복호화 실패(계정 변경 등): 키 재입력 유도.

---

## 8. 성능 목표
- 조회는 캐시(세션 메모리) 후 즉시. 저장은 소량.

---

## 9. 보안/프라이버시 고려사항
- 비밀정보는 메모리 상 노출 최소화(필요 시점에만 조회).
- 진단 export/로그에 비밀정보 절대 미포함(마스킹 강제).
- 오디오 보관 정책: 기본 "처리 후 삭제", 보관일 초과분 삭제 잡 협조.

---

## 10. 테스트 항목
- 단위: set/get/delete, 마스킹 규칙, retention 검증(mock store).
- 통합: 실제 DPAPI 저장/조회(플랫폼 테스트).
- 엣지: 없는 키 조회, 접근 실패, 마스킹 누락 방지 회귀.

---

## 11. 관련 Phase와 구현 범위
- **P2**: 키 저장/조회 + 로그 마스킹(클라우드 provider 도입과 함께).
- **P3**: 보관 정책 집행, 진단 export 마스킹 검증.
- **P4**: 원격 페어링 시크릿 관리.

---

## 12. 미결정 사항
- DPAPI vs Credential Manager 최종 선택.
- 키 캐시 수명(메모리 유지 시간).
- 보관 정책 삭제 잡 실행 주체(C10/C11/C6 협의).
