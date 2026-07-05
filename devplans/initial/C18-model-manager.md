# C18. ModelManager 개발계획서

| 항목 | 내용 |
|------|------|
| 구성요소 ID | C18 |
| 이름 | ModelManager (모델 관리) |
| 계층 | Core Engine |
| 관련 Phase | P0/P1(최소), P3(핵심) |
| 상위 문서 | `README.md` |

---

## 1. 목적/책임
로컬 STT(Whisper) 모델의 목록/다운로드/캐시/검증/선택을 관리하고, Ollama 모델 목록 조회를 돕는다.

- 사용 가능한 Whisper 모델 카탈로그 제공.
- 다운로드(진행률/재개/검증)와 캐시 경로 관리.
- 활성 모델 선택 상태 관리.
- Ollama 설치/모델 목록 조회(연결 확인).

**책임이 아닌 것**: 실제 추론(C2/C3), 설치 프로그램 번들(C16), 비밀정보(C19).

---

## 2. 선택 근거와 대안 검토
- **런타임 관리로 분리**: 모델은 설치본에 무조건 번들하지 않고(용량), 최초 실행 시 선택 다운로드(벤치마크 표준). 따라서 설치(C16)와 별개의 런타임 구성요소가 필요.
- **오프라인 경로 지정 지원**: 인터넷 제한 환경 위해 로컬 모델 폴더 지정 옵션.
- **checksum 검증**: 손상/부분 다운로드 방지.

---

## 3. 공개 인터페이스 계약
- `list_catalog() -> [ModelCatalogItem]`: 지원 모델(크기/언어/요구사항).
- `list_installed() -> [InstalledModel]`.
- `ensure(model_id, on_progress) -> ModelPath`: 없으면 다운로드+검증 후 경로 반환.
- `set_active(model_id)` / `get_active() -> model_id`.
- `remove(model_id)`.
- `set_custom_path(path)`: 오프라인 모델 폴더 지정.
- `list_ollama_models() -> [OllamaModel]`: Ollama 연결/목록(협조).

`on_progress(downloaded, total, state)` 콜백.

---

## 4. 입력/출력 데이터와 상태 전이
- 입력: 모델 선택/다운로드 요청.
- 출력: 모델 경로, 설치 상태.
- 모델 상태: `not_installed → downloading → verifying → installed`(+ `error`, `paused`).

---

## 5. 의존 구성요소와 호출 관계
- **호출자**: C2 STT(경로 확인/ensure), C14 설정 UI(모델 선택/다운로드), C21 Onboarding(초기 준비), C3 LLM(Ollama 목록 협조).
- **의존**: 네트워크, 파일시스템(`%APPDATA%\STT-AIO\models`), C11 Config(활성 모델/경로), C20 Logging.

---

## 6. 내부 설계
### 6.1 구조
- `catalog.py`: 지원 모델 메타(이름, 크기, URL/repo, checksum, 요구 VRAM).
- `downloader.py`: 재개 가능 다운로드, 진행률, 검증.
- `store_paths.py`: 캐시 경로/오프라인 경로 규칙.
- `active.py`: 활성 모델 선택 상태(Config 연동).
- `ollama_probe.py`: Ollama 연결/목록 조회.

### 6.2 ensure 절차
1. 활성/요청 모델이 설치됨인지 확인(경로+checksum).
2. 없으면 catalog에서 소스 조회 → 임시 파일로 다운로드(진행률 콜백).
3. checksum 검증 → 성공 시 최종 경로로 이동, 상태 installed.
4. 경로 반환.

### 6.3 다운로드 견고성
- 재개(Range) 지원, 중단 시 임시 파일 유지.
- 디스크 공간 사전 확인.
- 프록시/사내 인증서 환경 오류를 사용자 메시지에 반영.

---

## 7. 오류/폴백/재시도 정책
- 네트워크 실패: 재시도/재개 안내, 수동 재시도 버튼(UI).
- checksum 불일치: 파일 삭제 후 재다운로드 유도.
- 디스크 부족: 필요한 공간 명시.
- 오프라인: custom_path 사용 안내.

---

## 8. 성능 목표
- 다운로드는 대역폭 제약이 지배적 → UI 진행률/취소 필수.
- 설치 여부 확인은 즉시(경로/메타 캐시).

---

## 9. 보안/프라이버시 고려사항
- 신뢰 가능한 소스에서만 다운로드, checksum 검증 필수.
- 다운로드 URL/경로는 로그 가능(민감정보 아님), 키는 무관.

---

## 10. 테스트 항목
- 단위: catalog 파싱, checksum 검증, 상태 전이, 경로 규칙(mock 다운로드).
- 통합: 실제 소형 모델 다운로드→검증→C2 사용.
- 엣지: 중단/재개, 디스크 부족, 손상 파일, 오프라인 custom_path.

---

## 11. 관련 Phase와 구현 범위
- **P0/P1**: 최소 — 활성 모델 경로 확인/존재 검사/친절한 실패 메시지.
- **P3**: 전체 — 카탈로그/다운로드/진행률/검증/UI 연동, Onboarding.

---

## 12. 미결정 사항
- 지원 모델 카탈로그 범위(tiny~large-v3-turbo 중 무엇).
- 모델 소스(HF repo 등)와 배포 정책.
- 기본 다운로드 모델(GPU 유무 결정에 종속).
