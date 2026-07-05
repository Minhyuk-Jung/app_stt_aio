# STT-AIO 릴리스 가이드 (P6)

> `docs/release_checklist.md` · `docs/update_policy.md` · `.github/workflows/release.yml`

## 1. 일상 개발 검증

```bash
python -m pytest tests/ -q --ignore=tests/ui
python scripts/smoke/release_checklist_smoke.py
python scripts/smoke/verify_ci_workflow.py
```

## 2. 로컬 전체 빌드 + 체크리스트 (#1/#2)

```bash
STT_AIO_RELEASE_BUILD=1 python scripts/smoke/release_checklist_smoke.py
```

## 2b. 릴리스 전 통합 게이트

```bash
# CI 정의 + 태그 검증 + (선택) 전체 빌드 스모크
python scripts/smoke/pre_release_gate.py --tag v0.2.0 --build

# Release 게시 후 원격 manifest 확인
STT_AIO_MANIFEST_URL=https://github.com/OWNER/REPO/releases/download/v0.2.0/update-manifest.json \
  python scripts/release/verify_remote_manifest.py --expected-version 0.2.0
```

## 3. GitHub Releases (권장, #11)

### 태그 푸시 (자동)

1. `pyproject.toml` / `build-manifest.json` 버전 일치 확인
2. **`git tag v0.2.0`는 manifest version `0.2.0`과 일치해야 함** (`verify_release_tag.py`)
3. `git push origin v0.2.0`
4. `.github/workflows/release.yml` — build·smoke·tag 검증·manifest·Release 업로드
5. 앱 설정 `update.manifest_url` → Release의 `update-manifest.json` URL

### Release 게시 후 (#11)

```bash
STT_AIO_MANIFEST_URL=https://github.com/OWNER/REPO/releases/download/v0.2.0/update-manifest.json \
  python scripts/release/post_release_checklist.py --tag v0.2.0
```

### 수동 (로컬 산출물)

```bash
python build/build.py --portable
python build/build.py --installer --skip-pyinstaller --require-installer

# GitHub URL 자동 생성 (CI와 동일)
set GITHUB_REPOSITORY=OWNER/REPO
python scripts/release/prepare_release_manifest.py --github-release --tag v0.2.0 --print-gh-upload

gh release create v0.2.0 dist/installer/STT-AIO-Setup-*.exe dist/installer/update-manifest.json
```

## 4. 엄격 릴리스 스모크

```bash
STT_AIO_RELEASE_STRICT=1 ^
  STT_AIO_UPDATE_DOWNLOAD_URL=https://github.com/OWNER/REPO/releases/download/v0.2.0/STT-AIO-Setup-0.2.0.exe ^
  python scripts/smoke/release_checklist_smoke.py
```

## 5. CI green 확인 (#5b)

```bash
# gh CLI 설치 후
STT_AIO_CI_REQUIRE_GREEN=1 python scripts/smoke/verify_ci_workflow.py
```

## 6. 수동 잔여

- #12~#13: 설정 → 업데이트 확인 UI (`docs/qa_checklist.md`)
- 모바일 실기기: `docs/p4_mobile_e2e.md`
- 코드사인: `DECISIONS.md` 회의 후 C22 3단계
