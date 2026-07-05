# C6. Store 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C6 |
| 이름 | Store (SQLite 영속화) |
| 계층 | Core Engine |
| 관련 Phase | P1(최소), P2(확장), P3(히스토리) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
세션, 산출물(artifact), 모드, 사전, 설정을 로컬 SQLite에 영속화한다.

- 스키마 정의 및 버전 마이그레이션.
- CRUD 및 조회(히스토리, 세션별 artifact).
- 트랜잭션으로 일관성 보장(크래시 복구 NFR).

**책임이 아닌 것**: 비즈니스 로직(각 도메인 구성요소), 비밀정보 저장(C19), 오디오 바이너리 저장(파일 경로만 저장).

---

## 2. 선택 근거와 대안 검토
- **SQLite**: 로컬 단일 사용자, 트랜잭션·조회·마이그레이션이 필요 → 최적. 대안 JSON 파일은 조회/마이그레이션/동시성에 취약.
- **경로 저장 원칙**: 오디오는 파일로 두고 DB엔 경로만(대용량 blob 회피).
- **마이그레이션 필수**: 초기부터 schema_version 관리(후속 Phase에서 스키마 성장 확실).

---

## 3. 공개 인터페이스 계약
도메인별 저장소 인터페이스(Repository 패턴):
- `SessionRepo`: create, update_status, get, list(paging/filter), delete.
- `ArtifactRepo`: add(stage), get_by_session, update_text, latest_by_stage.
- `ModeRepo`: crud, seed_defaults, list.
- `DictionaryRepo`: crud, list_by_type.
- `SettingRepo`: get(key), set(key,value), get_all(비민감).
- `Migrator`: current_version, migrate_to_latest.

모든 쓰기는 트랜잭션 경계 안에서 수행.

---

## 4. 입력/출력 데이터와 상태 전이
### 스키마(초기)
```
schema_meta(version)
sessions(id, created_at, source, mode_id, audio_path, status)
artifacts(id, session_id, stage, text, provider, prompt_snapshot, created_at)
modes(id, name, target_stage, inject_stage, correction_prompt, report_prompt,
      stt_provider?, llm_provider?, is_default, updated_at)
dictionaries(id, term, replacement, type, enabled)
settings(key, value, updated_at)
```
- 인덱스: artifacts(session_id, stage), sessions(created_at).
- status(sessions): recording|processing|done|error|canceled.

---

## 5. 의존 구성요소와 호출 관계
- **호출자**: C4 Pipeline(artifact 저장), C10 Session(세션), C7 Mode, C11 Config, C13 Workbench(조회), C8 Exporter(조회).
- **의존**: SQLite 드라이버, C20 Logging.
- **경계 원칙**: 상위는 Repository만 사용, 원시 SQL 직접 접근 금지.

---

## 6. 내부 설계
### 6.1 구조
- `db.py`: 연결/트랜잭션/PRAGMA(WAL 등) 관리.
- `migrations/`: 버전별 스키마 변경 스크립트 + 순차 적용기.
- `repos/`: 도메인별 Repository.
- `models.py`: 행↔도메인 객체 매핑.

### 6.2 초기화 절차
1. 사용자 데이터 경로(`%APPDATA%\STT-AIO\app.db`) 확인/생성(C11 경로 규칙).
2. 연결 후 PRAGMA(WAL, foreign_keys=ON) 설정.
3. `schema_meta` 확인 → 필요한 마이그레이션 순차 적용.
4. 기본 모드 seed(없을 때만).

### 6.3 마이그레이션 규칙
- 각 마이그레이션은 순번 + up 스크립트. 절대 기존 스크립트 수정 금지(추가만).
- 적용 전 자동 백업(파일 복사) 옵션.

### 6.4 동시성
- 단일 쓰기 연결 + 읽기 연결 분리 또는 짧은 트랜잭션으로 잠금 최소화.
- UI 스레드에서 무거운 조회 금지(워커에서).

---

## 7. 오류/폴백/재시도 정책
- DB 잠금(busy): 짧은 재시도(timeout) 후 실패 로그.
- 마이그레이션 실패: 백업 복원 안내 + 앱은 안전 모드(읽기 전용) 진입 고려.
- 손상 DB: 감지 시 백업/재생성 경로 안내(데이터 보존 우선).

---

## 8. 성능 목표
- 일반 CRUD 수 ms.
- 히스토리 페이징 조회는 인덱스 기반으로 빠르게.
- artifact 텍스트가 커도 조회는 필요 컬럼만.

---

## 9. 보안/프라이버시 고려사항
- API 키/비밀정보는 저장하지 않음(C19 사용).
- 오디오/텍스트 보관은 C11 보관 정책과 연동(만료 삭제 잡).
- 필요 시 DB 암호화(SQLCipher)는 백로그로 검토.

---

## 10. 테스트 항목
- 단위: 각 Repo CRUD, 트랜잭션 롤백, 마이그레이션 순차 적용, seed 멱등성.
- 통합: 파이프라인 저장→조회 일관성, 크래시 시 미완 트랜잭션 복구.
- 엣지: 대량 세션 페이징, 동시 읽기/쓰기, 잠금 상황.

---

## 11. 관련 Phase와 구현 범위
- **P1**: sessions/settings 최소 스키마 + 기본 Repo(주입 앱이므로 최소).
- **P2**: artifacts/modes/dictionaries 확장, 마이그레이션 체계.
- **P3**: 히스토리 조회/페이징, 보관 정책 삭제 잡.

---

## 12. 미결정 사항
- 재가공 시 artifact 갱신 vs 버전 이력(테이블 설계에 영향).
- DB 암호화 도입 여부/시점.
- 자동 백업 주기/보관 개수.
