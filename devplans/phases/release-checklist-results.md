# Release Checklist — 자동 검증 결과

자동 기록: `release_checklist_smoke.py` (2026-07-05)

> 수동 항목(설치·실기기·매니페스트 게시)은 `docs/release_checklist.md` 참고.
> 릴리스 모드: `STT_AIO_RELEASE_BUILD=1 python scripts/smoke/release_checklist_smoke.py`
> 엄격 모드: `STT_AIO_RELEASE_STRICT=1` (dist/manifest 없으면 fail)
> 매니페스트 URL: `STT_AIO_UPDATE_DOWNLOAD_URL=https://…/Setup.exe`
> 릴리스 태그: `STT_AIO_RELEASE_TAG=v0.2.0` (미설정 시 manifest version에서 추론)
> CI green 필수: `STT_AIO_CI_REQUIRE_GREEN=1` (gh CLI 필요)

| 항목 | 날짜 | 환경 | 결과 |
|------|------|------|------|
| pytest (UI 제외) | 2026-07-05 | Python 3.10.9 / Windows | pass |
| ko_wer 회귀 (non-integration) | 2026-07-05 | Python 3.10.9 / Windows | pass |
| update_ui_automation | 2026-07-05 | Python 3.10.9 / Windows | pass |
| tunnel_check | 2026-07-05 | Python 3.10.9 / Windows | pass |
| build.py --portable | 2026-07-05 | Python 3.10.9 / Windows | pass |
| build.py --installer | 2026-07-05 | Python 3.10.9 / Windows | pass |
| verify_bundle | 2026-07-05 | Python 3.10.9 / Windows | pass |
| bundle_smoke | 2026-07-05 | Python 3.10.9 / Windows | pass |
| dist_freshness | 2026-07-05 | Python 3.10.9 / Windows | pass |
| verify_release_tag | 2026-07-05 | Python 3.10.9 / Windows | pass |
| verify_installer | 2026-07-05 | Python 3.10.9 / Windows | pass |
| generate_update_manifest | 2026-07-05 | Python 3.10.9 / Windows | fail(1) |
| prepare_release_manifest | 2026-07-05 | Python 3.10.9 / Windows | pass |
| verify_remote_manifest | 2026-07-05 | Python 3.10.9 / Windows | skip: no STT_AIO_MANIFEST_URL |
| verify_update_manifest | 2026-07-05 | Python 3.10.9 / Windows | fail(1) |
| installer_smoke | 2026-07-05 | Python 3.10.9 / Windows | pass |
| record_nfr_results | 2026-07-05 | Python 3.10.9 / Windows | pass |
| ci_workflow_definition | 2026-07-05 | Python 3.10.9 / Windows | pass |
| ci_github_run | 2026-07-05 | Python 3.10.9 / Windows | skip: gh CLI not available |
| ci_release_github_run | 2026-07-05 | Python 3.10.9 / Windows | skip: gh CLI not available |
| NFR packaged gate | 2026-07-05 | Python 3.10.9 / Windows | pass |
| Cloudflare Tunnel CLI | 2026-07-05 | Python 3.10.9 / Windows | skip |

### pytest (UI 제외)

```
........................................................................ [ 13%]
........................................................................ [ 27%]
........................................................................ [ 41%]
...............................................s........................ [ 54%]
........................................................................ [ 68%]
........................................................................ [ 82%]
........................................................................ [ 96%]
.....................                                                    [100%]
524 passed, 1 skipped in 31.61s
```

### ko_wer 회귀 (non-integration)

```
....                                                                     [100%]
4 passed, 1 deselected in 0.54s
```

### update_ui_automation

```
..................                                                       [100%]
18 passed in 1.88s
```

### tunnel_check

```
status=skip
reason=cloudflared not on PATH
```

### build.py --portable

```
Manifest: C:\Users\MJ_Home\workspaces\app_stt_aio\dist\installer\build-manifest.json
```

### build.py --installer

```
ll
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6\vcruntime140.dll
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6\vcruntime140_1.dll
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6\_config.py
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6\_git_shiboken_module_version.py
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6\__init__.py
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6-6.8.3.dist-info\INSTALLER
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6-6.8.3.dist-info\LicenseRef-Qt-Commercial.txt
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6-6.8.3.dist-info\METADATA
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6-6.8.3.dist-info\RECORD
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6-6.8.3.dist-info\top_level.txt
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\shiboken6-6.8.3.dist-info\WHEEL
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\stt_aio.egg-info\dependency_links.txt
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\stt_aio.egg-info\entry_points.txt
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\stt_aio.egg-info\PKG-INFO
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\stt_aio.egg-info\requires.txt
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\stt_aio.egg-info\SOURCES.txt
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\stt_aio.egg-info\top_level.txt
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\tokenizers\tokenizers.pyd
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\tqdm-4.68.3.dist-info\entry_points.txt
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\tqdm-4.68.3.dist-info\INSTALLER
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\tqdm-4.68.3.dist-info\METADATA
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\tqdm-4.68.3.dist-info\RECORD
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\tqdm-4.68.3.dist-info\top_level.txt
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\tqdm-4.68.3.dist-info\WHEEL
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\tqdm-4.68.3.dist-info\licenses\LICENCE
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\yaml\_yaml.cp310-win_amd64.pyd
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\_sounddevice_data\portaudio-binaries\libportaudio64bit-asio.dll
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\_sounddevice_data\portaudio-binaries\libportaudio64bit.dll
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\..\dist\STT-AIO\_internal\_sounddevice_data\portaudio-binaries\README.md
   Compressing: C:\Users\MJ_Home\workspaces\app_stt_aio\build\SMARTSCREEN.txt
   Compressing Setup program executable
   Updating version info (Setup.exe)
   Updating manifest (Setup.exe)


Successful compile (144.250 sec). Resulting Setup program filename is:
C:\Users\MJ_Home\workspaces\app_stt_aio\dist\installer\STT-AIO-Setup-0.1.0.exe
Manifest: C:\Users\MJ_Home\workspaces\app_stt_aio\dist\installer\build-manifest.json
```

### verify_bundle

```
verify_bundle_ok dir=dist\STT-AIO
```

### bundle_smoke

```
bundle_smoke: verify_bundle
verify_bundle_ok dir=C:\Users\MJ_Home\workspaces\app_stt_aio\scripts\smoke\..\..\dist\STT-AIO
install_smoke_ok exe=C:\Users\MJ_Home\workspaces\app_stt_aio\scripts\smoke\..\..\dist\STT-AIO\STT-AIO.exe size=9363019 version=0.1.0
```

### dist_freshness

```
pass
```

### verify_release_tag

```
pass
```

### verify_installer

```
verify_installer_ok setup=C:\Users\MJ_Home\workspaces\app_stt_aio\dist\installer\STT-AIO-Setup-0.1.0.exe
```

### generate_update_manifest

```
FAIL download_url is placeholder \u2014 set STT_AIO_UPDATE_DOWNLOAD_URL or pass --download-url
```

### prepare_release_manifest

```
wrote C:\Users\MJ_Home\workspaces\app_stt_aio\dist\installer\update-manifest.json
OK wrote C:\Users\MJ_Home\workspaces\app_stt_aio\dist\installer\update-manifest.json
version=0.1.0
download_url=https://github.com/OWNER/REPO/releases/download/v0.1.0/STT-AIO-Setup-0.1.0.exe
checksum_sha256=f22db0284d445ef009ca3dfd49aa6716b08730b2ab324175a58bfa892368152b
manifest_url=https://github.com/OWNER/REPO/releases/download/v0.1.0/update-manifest.json
# Set update.manifest_url in app settings to manifest_url after release upload
```

### verify_remote_manifest

```
skip: no STT_AIO_MANIFEST_URL
```

### verify_update_manifest

```
FAIL update-manifest.json missing
```

### installer_smoke

```
installer_smoke: verify_installer
verify_installer_ok setup=C:\Users\MJ_Home\workspaces\app_stt_aio\dist\installer\STT-AIO-Setup-0.1.0.exe
installer_smoke: silent install -> C:\Users\MJ_Home\AppData\Local\Temp\stt-aio-smoke-94541ff3
installer_smoke: upgrade reinstall (same dir)
installer_smoke: uninstall
installer_smoke_ok setup=C:\Users\MJ_Home\workspaces\app_stt_aio\dist\installer\STT-AIO-Setup-0.1.0.exe version=0.1.0
```

### record_nfr_results

```
wrote C:\Users\MJ_Home\workspaces\app_stt_aio\devplans\phases\P5-nfr-results.md
```

### ci_workflow_definition

```
pass
```

### ci_github_run

```
skip: gh CLI not available
```

### ci_release_github_run

```
skip: gh CLI not available
```

### NFR packaged gate

```
packaged NFR pass
```

체크리스트: `docs/release_checklist.md`
