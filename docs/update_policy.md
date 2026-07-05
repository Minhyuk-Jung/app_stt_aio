# STT-AIO 업데이트 정책 (C22)

> P5 DoD 필수 산출물 (`README.md` §8.1)

## 단계적 롤아웃 (`C22-updater.md` §6.2)

| 단계 | 내용 | 현재 상태 |
|------|------|----------|
| 1단계 | 버전 확인 + 릴리스 노트 + 브라우저 열기 | ✅ |
| 2단계 | 앱 내 다운로드 + SHA-256 검증 + 설치 실행 | ✅ |
| 3단계 | 코드사인 후 자동 업데이트 옵션 | ❌ (미결정) |

## 매니페스트 형식

예시 파일: `build/sample-update-manifest.json`  
릴리스 생성: `python build/generate_update_manifest.py` (`build-manifest.json` 필요)  
**릴리스 게시(실 URL)**: `python scripts/release/prepare_release_manifest.py --download-url https://…`

```bash
# 태그·manifest 버전 일치 (릴리스 전)
python scripts/release/verify_release_tag.py --tag v0.2.0

# 개발/CI 템플릿 (placeholder 허용)
python build/generate_update_manifest.py --allow-placeholder

# 릴리스 (strict, 실 URL 필수)
STT_AIO_UPDATE_DOWNLOAD_URL=https://github.com/OWNER/REPO/releases/download/v0.2.0/STT-AIO-Setup-0.2.0.exe \
  python scripts/release/prepare_release_manifest.py --print-gh-upload

# Release 게시 후 원격 manifest 검증 (#11)
STT_AIO_MANIFEST_URL=https://github.com/OWNER/REPO/releases/download/v0.2.0/update-manifest.json \
  python scripts/release/verify_remote_manifest.py --expected-version 0.2.0
```

## CI (P6)

- `build.yml`: `pytest tests/ -q --ignore=tests/ui` (로컬 스모크와 동일)
- workflow 정의: `python scripts/smoke/verify_ci_workflow.py`
- CI green 필수: `STT_AIO_CI_REQUIRE_GREEN=1 python scripts/smoke/verify_ci_workflow.py` (gh CLI)

```json
{
  "version": "0.2.0",
  "download_url": "https://example.com/STT-AIO-Setup-0.2.0.exe",
  "checksum_sha256": "<64자 hex>",
  "release_notes": "변경 사항 요약",
  "mandatory": false,
  "notes_by_version": {
    "0.2.0": "상세 릴리스 노트"
  }
}
```

- `checksum_sha256`가 없으면 **브라우저 수동 다운로드**만 제공합니다.
- `mandatory: true`이면 UI에서 "나중에" 옵션을 숨깁니다.

## 설정 (C11)

| 키 | 설명 | 기본값 |
|----|------|--------|
| `update.manifest_url` | 원격 매니페스트 URL | (빈 문자열) |
| `update.auto_check` | 앱 시작 시 자동 확인 | `false` |

## 보안 원칙 (C22 §6.3)

1. checksum 검증 통과 전 설치본 실행 금지
2. 코드 서명 검증은 코드사인 도입 후 3단계에서 활성화
3. 확인 실패 시 조용히 무시 (시작 시 자동 확인)

## 실패 시 폴백 (C22 §7)

1. 다운로드/검증 실패 → 브라우저 수동 다운로드 안내
2. 네트워크 없음 → 다음 기회에 재시도

## 미결정 (`C22` §12, `README` §14)

- 매니페스트 호스팅 위치 (GitHub Releases / 자체 CDN 등)
- 코드사인 적용 시점
- 강제 업데이트(`mandatory`) 운영 정책
