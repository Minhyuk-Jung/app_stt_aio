# C16 installer smoke — silent install, version, upgrade, uninstall (plan §10).
param(
    [string]$SetupExe = "",
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\version_check.ps1"

$root = Resolve-Path "$PSScriptRoot\..\.."
$py = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py" }
$expectedVersion = Get-ExpectedVersionFromManifest -Root $root

if (-not $SetupExe) {
    $manifest = Join-Path $root "dist\installer\build-manifest.json"
    if (-not (Test-Path $manifest)) {
        Write-Error "installer_smoke: build-manifest.json not found (run python build/build.py --installer)"
    }
    $json = Get-Content $manifest -Raw | ConvertFrom-Json
    $installer = $json.artifacts | Where-Object { $_.type -eq "installer" } | Select-Object -First 1
    if (-not $installer) {
        Write-Error "installer_smoke: no installer artifact in manifest"
    }
    $SetupExe = Join-Path $root ($installer.path -replace "/", "\")
    if (-not $expectedVersion) {
        $expectedVersion = $json.version
    }
}

if (-not (Test-Path $SetupExe)) {
    Write-Error "installer_smoke: setup not found: $SetupExe"
}

Write-Host "installer_smoke: verify_installer"
& $py "$root\build\verify_installer.py" --setup $SetupExe
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $InstallDir) {
    $InstallDir = Join-Path $env:TEMP ("stt-aio-smoke-" + [guid]::NewGuid().ToString("n").Substring(0, 8))
}

$installArgs = @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/DIR=$InstallDir"
)

Write-Host "installer_smoke: silent install -> $InstallDir"
$proc = Start-Process -FilePath $SetupExe -ArgumentList $installArgs -Wait -PassThru
if ($proc.ExitCode -ne 0) {
    Write-Error "installer_smoke: setup failed exit=$($proc.ExitCode)"
}

$exe = Join-Path $InstallDir "STT-AIO.exe"
$version = Test-SttAioExeVersion -Exe $exe -ExpectedVersion $expectedVersion

Write-Host "installer_smoke: packaged functional smoke (--smoke)"
$env:QT_QPA_PLATFORM = "offscreen"
& $exe --smoke
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue

Write-Host "installer_smoke: upgrade reinstall (same dir)"
$upgrade = Start-Process -FilePath $SetupExe -ArgumentList $installArgs -Wait -PassThru
if ($upgrade.ExitCode -ne 0) {
    Write-Error "installer_smoke: upgrade setup failed exit=$($upgrade.ExitCode)"
}
if (-not (Test-Path $exe)) {
    Write-Error "installer_smoke: exe missing after upgrade"
}
$versionAfter = Test-SttAioExeVersion -Exe $exe -ExpectedVersion $expectedVersion
if ($versionAfter -ne $version) {
    Write-Error "installer_smoke: version changed after upgrade ($version -> $versionAfter)"
}

$uninstaller = Join-Path $InstallDir "unins000.exe"
if (-not (Test-Path $uninstaller)) {
    Write-Error "installer_smoke: unins000.exe missing"
}

Write-Host "installer_smoke: uninstall"
$unproc = Start-Process -FilePath $uninstaller -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES") -Wait -PassThru
if ($unproc.ExitCode -ne 0) {
    Write-Error "installer_smoke: uninstall failed exit=$($unproc.ExitCode)"
}
if (Test-Path $exe) {
    Write-Error "installer_smoke: exe still present after uninstall"
}

Write-Host "installer_smoke_ok setup=$SetupExe version=$version"
exit 0
