# STT-AIO 수동 릴리스 런북

> **현재 자동 상태** (`release-checklist-status.md` 기준, 2026-07-05)  
> ☑ 완료: #3~#10 · ◐ 부분: #1/#2, #5b, #11, #12/#13 · ☐ 정책/선택: 코드사인, 실기기 E2E

이 문서만 위에서 아래로 따라 하면 **첫 GitHub Release까지** 완료할 수 있습니다.

---

## 0. 수동 작업 한눈에 보기

| 우선순위 | 항목 | 체크리스트 | 예상 시간 | 필수? |
|---------|------|-----------|----------|------|
| A | 로컬 fresh 빌드 + 스모크 | #1, #2 | 30~60분 | **릴리스 전 필수** |
| B | GitHub push → CI green | #5b | 10~20분 | **릴리스 전 필수** |
| C | 버전·태그 맞추고 Release 푸시 | #11 | 5~15분 | **릴리스 필수** |
| D | Release 후 manifest URL 검증·앱 설정 | #11 잔여 | 5분 | **릴리스 필수** |
| E | 설치본에서 업데이트 UI 확인 | #12, #13 | 10분 | **권장** |
| F | 모바일 실기기 E2E | `qa_checklist` §9 | 30분+ | 선택 |
| G | cloudflared 실환경 | tunnel_live | 15분+ | 선택 |
| H | 코드사인·C22 3단계 | `DECISIONS.md` | 미정 | 상용화 시 |

---

## 1. 사전 준비 (한 번만)

### 1.1 도구

- [ ] Windows 10/11, 프로젝트 루트: `c:\Users\MJ_Home\workspaces\app_stt_aio`
- [ ] Python venv: `.venv\Scripts\python.exe` (Anaconda base 말고 **반드시 venv**)
- [ ] Git 원격 저장소 연결 (`git remote -v` → `github.com/OWNER/REPO`)
- [ ] (권장) [GitHub CLI](https://cli.github.com/) 설치 → `gh auth login`

### 1.2 환경 변수 (릴리스 시 세션마다)

PowerShell 예시 — `OWNER/REPO`, `v0.1.0`을 실제 값으로 바꿉니다.

```powershell
cd c:\Users\MJ_Home\workspaces\app_stt_aio

$env:GITHUB_REPOSITORY = "OWNER/REPO"   # 예: "myuser/stt-aio"
$VERSION = "0.1.0"                       # pyproject.toml과 동일
$TAG = "v$VERSION"
```

### 1.3 버전 확인

```powershell
.\.venv\Scripts\python.exe -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
# → 0.1.0 이 나와야 함. 바꿀 거면 pyproject.toml + core/version.py 먼저 수정 후 빌드
```

---

## 2. Phase A — 로컬 fresh 빌드 (#1, #2)

**목표**: 오래된 `dist/`가 아닌, 지금 코드 기준 패키지·인스톨러 생성.

### 2.1 통합 게이트 (권장, 한 방)

```powershell
.\.venv\Scripts\python.exe scripts/smoke/pre_release_gate.py --tag $TAG --build
```

- 소요: **30~60분** (PyInstaller + Inno Setup 포함)
- 성공: 마지막에 `release_checklist_smoke` exit 0
- 실패 시: `devplans/phases/release-checklist-results.md` 에서 실패 항목 확인

### 2.2 또는 스모크만

```powershell
$env:STT_AIO_RELEASE_BUILD = "1"
$env:STT_AIO_RELEASE_TAG = $TAG
.\.venv\Scripts\python.exe scripts/smoke/release_checklist_smoke.py
```

### 2.3 산출물 확인

```powershell
Test-Path dist\STT-AIO\STT-AIO.exe
Test-Path dist\installer\STT-AIO-Setup-$VERSION.exe
Test-Path dist\installer\build-manifest.json
Test-Path dist\installer\build-stamp.json
```

### 2.4 태그·manifest 정합 (빌드 후)

```powershell
.\.venv\Scripts\python.exe scripts/release/verify_release_tag.py --tag $TAG
# OK tag v0.1.0 matches build-manifest version 0.1.0
```

### 2.5 체크리스트 갱신 확인

```powershell
Get-Content devplans\phases\release-checklist-status.md | Select-String "#1|#2"
# #1, #2 가 ☑ auto-pass 이면 Phase A 완료
```

---

## 3. Phase B — GitHub CI green (#5b)

**목표**: `build.yml` workflow가 GitHub에서 success.

### 3.1 변경사항 push

```powershell
git status
git add -A
git commit -m "chore: release prep v$VERSION"
git push origin main
# 브랜치명이 master면 origin master
```

### 3.2 CI 확인 (방법 택1)

**방법 A — gh CLI**

```powershell
gh run list --workflow build.yml --limit 3
gh run watch   # 최신 run ID로
$env:STT_AIO_CI_REQUIRE_GREEN = "1"
.\.venv\Scripts\python.exe scripts/smoke/verify_ci_workflow.py
```

**방법 B — 브라우저**

1. GitHub → Actions → **Build Windows**
2. 최근 run이 초록색(success)인지 확인

### 3.3 완료 기준

- [ ] `build.yml` 최근 run **success**
- [ ] (선택) `verify_ci_workflow.py`에서 `github_run=pass`

---

## 4. Phase C — GitHub Release 게시 (#11)

**목표**: 태그 푸시 → `release.yml`이 빌드·검증·Release 업로드.

### 4.1 릴리스 전 빠른 검증 (선택, ~1분)

```powershell
.\.venv\Scripts\python.exe scripts/smoke/pre_release_gate.py --tag $TAG --quick
```

### 4.2 로컬에서 manifest 미리보기 (선택)

```powershell
$env:GITHUB_REPOSITORY = "OWNER/REPO"
.\.venv\Scripts\python.exe scripts/release/prepare_release_manifest.py `
  --github-release --tag $TAG --print-gh-upload
```

### 4.3 태그 생성·푸시

```powershell
# 버전이 이미 올라갔는지 확인
git tag -l "v*"

git tag $TAG                    # 이미 있으면: git tag -d $TAG 후 재생성
git push origin $TAG
```

### 4.4 Release workflow 확인

```powershell
gh run list --workflow release.yml --limit 3
# 또는 GitHub Actions → Release
```

성공 시 Release 페이지에 다음 파일이 있어야 합니다.

- `STT-AIO-Setup-{VERSION}.exe`
- `update-manifest.json`
- `build-manifest.json`
- portable zip, `SMARTSCREEN.txt`

### 4.5 Release 후 원격 manifest 검증

```powershell
$MANIFEST_URL = "https://github.com/OWNER/REPO/releases/download/$TAG/update-manifest.json"

.\.venv\Scripts\python.exe scripts/release/post_release_checklist.py `
  --tag $TAG --manifest-url $MANIFEST_URL
```

출력된 `update.manifest_url=...` 값을 복사해 둡니다.

---

## 5. Phase D — 앱에 업데이트 URL 설정 (#11 잔여)

**목표**: 설치된 앱이 Release의 manifest를 볼 수 있게 함.

### 5.1 설치 (아직 안 했다면)

```powershell
Start-Process "dist\installer\STT-AIO-Setup-$VERSION.exe"
# 또는 Release에서 받은 exe
```

### 5.2 앱 설정

1. 트레이 아이콘 → **설정**
2. **일반** 탭 → **업데이트** 섹션
3. **매니페스트 URL**에 Phase C에서 받은 URL 붙여넣기  
   예: `https://github.com/OWNER/REPO/releases/download/v0.1.0/update-manifest.json`
4. (선택) **앱 시작 시 업데이트 자동 확인** 체크
5. 설정 창 닫기 (자동 저장)

---

## 6. Phase E — 설치본 UI 확인 (#12, #13)

pytest auto-proxy(◐)는 통과했지만, **실제 설치본**에서 한 번 확인합니다.  
상세: `docs/qa_checklist.md` §8.

### 6.1 #12 — 업데이트 확인 UI

| 단계 | 동작 | 기대 결과 |
|------|------|----------|
| 1 | 설정 → **업데이트 확인** 클릭 | 다이얼로그 표시 |
| 2a | manifest URL **비움** → 앱 재시작 | 오류 없이 조용히 스킵 (`qa` 8.2) |
| 2b | manifest URL **설정** + 구버전 설치 상태 | "업데이트 사용 가능" 또는 최신 안내 |

**구버전 시뮬레이션**: Release에 `0.2.0` manifest를 올리고, 로컬은 `0.1.0` 설치본 유지.

### 6.2 #13 — 다운로드·설치 흐름

| 단계 | 동작 | 기대 결과 |
|------|------|----------|
| 1 | 업데이트 다이얼로그 → **다운로드 및 설치** | 진행률 표시 |
| 2 | 완료 후 **예** 클릭 | 설치 프로그램 실행, 앱 종료 |
| 3 | (실패 시) **브라우저에서 열기** | download URL 브라우저 오픈 |

### 6.3 트레이 메뉴 경로

- 트레이 → **업데이트 확인** (설정과 동일 다이얼로그)

### 6.4 기록

`docs/release_checklist.md` #12, #13 에 ☑ 표시.

---

## 7. 선택 작업 (릴리스 차단 아님)

### 7.1 모바일 실기기 E2E

- 가이드: `docs/p4_mobile_e2e.md`
- 체크리스트: `docs/qa_checklist.md` §9
- 필요: Windows + 스마트폰 같은 LAN 또는 Tunnel

### 7.2 Cloudflare Tunnel 실환경

```powershell
# cloudflared 설치 후
.\.venv\Scripts\python.exe scripts/smoke/tunnel_live_smoke.py
```

### 7.3 코드사인 (C22 3단계)

- 현재: **미결정** (`DECISIONS.md`)
- 미서명 시 SmartScreen 경고 → `dist/installer/SMARTSCREEN.txt` 안내
- 상용 배포 전 회의에서 확정

### 7.4 정책 회의 (코드 밖)

`DECISIONS.md` §다음 확정 회의 안건:

- GPU 번들·기본 모델 크기
- 온보딩 필수 단계

---

## 8. 릴리스 완료 체크리스트 (복사용)

```
Phase A  로컬 빌드 (#1/#2)
  [ ] pre_release_gate --build 성공
  [ ] verify_release_tag OK
  [ ] release-checklist-status #1/#2 ☑

Phase B  CI (#5b)
  [ ] git push
  [ ] build.yml run success

Phase C  Release (#11)
  [ ] git push tag vX.Y.Z
  [ ] release.yml success
  [ ] post_release_checklist OK

Phase D  앱 설정
  [ ] update.manifest_url 설정

Phase E  UI (#12/#13)
  [ ] 설정에서 업데이트 확인
  [ ] 다운로드/브라우저 폴백 (선택)

선택
  [ ] 모바일 E2E
  [ ] tunnel_live
  [ ] 코드사인 회의
```

---

## 9. 자주 쓰는 명령 모음

```powershell
# 일상 검증 (~1분, 빌드 없음)
.\.venv\Scripts\python.exe -m pytest tests/ -q --ignore=tests/ui
.\.venv\Scripts\python.exe scripts/smoke/release_checklist_smoke.py

# CI 정의만 (~1초)
.\.venv\Scripts\python.exe scripts/smoke/verify_ci_workflow.py

# 엄격 릴리스 스모크 (실 URL 필요)
$env:STT_AIO_RELEASE_STRICT = "1"
$env:STT_AIO_UPDATE_DOWNLOAD_URL = "https://github.com/OWNER/REPO/releases/download/v0.1.0/STT-AIO-Setup-0.1.0.exe"
.\.venv\Scripts\python.exe scripts/smoke/release_checklist_smoke.py
```

---

## 10. 관련 문서

| 문서 | 용도 |
|------|------|
| `docs/release_guide.md` | 자동화·CI 상세 |
| `docs/release_checklist.md` | 공식 체크리스트 표 |
| `devplans/phases/release-checklist-status.md` | 최신 자동 매핑 상태 |
| `docs/update_policy.md` | C22 업데이트 정책 |
| `docs/qa_checklist.md` | 수동 QA 시나리오 |
