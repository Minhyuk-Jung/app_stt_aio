# C16 install smoke — verify bundle exists and PE/VERSION.txt version.
param(
    [string]$AppDir = "$PSScriptRoot\..\..\dist\STT-AIO"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\version_check.ps1"

$root = Resolve-Path "$PSScriptRoot\..\.."
$exe = Join-Path $AppDir "STT-AIO.exe"

if (-not (Test-Path $exe)) {
    Write-Error "Missing executable: $exe (run python build/build.py first)"
}

$size = (Get-Item $exe).Length
if ($size -lt 1024) {
    Write-Error "Executable too small ($size bytes): $exe"
}

$expected = Get-ExpectedVersionFromManifest -Root $root
$version = Test-SttAioExeVersion -Exe $exe -ExpectedVersion $expected

Write-Host "bundle_smoke: packaged functional smoke (--smoke)"
& $exe --smoke
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "install_smoke_ok exe=$exe size=$size version=$version"
