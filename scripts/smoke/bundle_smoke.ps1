# C16 post-build smoke — verify bundle policy + executable (plan §10).
param(
    [string]$AppDir = "$PSScriptRoot\..\..\dist\STT-AIO",
    [switch]$RequireExe,
    [switch]$RequireInstaller
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
$py = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py" }

Write-Host "bundle_smoke: verify_bundle"
& $py "$root\build\verify_bundle.py" --app-dir $AppDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exe = Join-Path $AppDir "STT-AIO.exe"
if (-not (Test-Path $exe)) {
    if ($RequireExe) {
        Write-Error "bundle_smoke: STT-AIO.exe not found at $exe (run python build/build.py first)"
        exit 1
    }
    Write-Host "bundle_smoke_skip: no executable (run python build/build.py first)"
    exit 0
}

& "$PSScriptRoot\install_smoke.ps1" -AppDir $AppDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($RequireInstaller) {
    & "$PSScriptRoot\installer_smoke.ps1"
    exit $LASTEXITCODE
}

exit 0
