# Shared PE / VERSION.txt checks for C16 smoke scripts.
function Get-ExpectedVersionFromManifest {
    param([string]$Root)
    $manifest = Join-Path $Root "dist\installer\build-manifest.json"
    if (-not (Test-Path $manifest)) {
        return ""
    }
    return (Get-Content $manifest -Raw | ConvertFrom-Json).version
}

function Test-SttAioExeVersion {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [string]$ExpectedVersion = ""
    )
    if (-not (Test-Path $Exe)) {
        throw "version_check: missing executable: $Exe"
    }

    $vi = (Get-Item $Exe).VersionInfo
    $peVersion = ($vi.ProductVersion -split '\s')[0].Trim()
    if ([string]::IsNullOrWhiteSpace($peVersion)) {
        throw "version_check: PE ProductVersion empty for $Exe"
    }

    $versionFile = Join-Path (Split-Path $Exe -Parent) "VERSION.txt"
    if (Test-Path $versionFile) {
        $fileVersion = (Get-Content $versionFile -Raw).Trim()
        if ([string]::IsNullOrWhiteSpace($fileVersion)) {
            throw "version_check: VERSION.txt empty beside $Exe"
        }
        if ($fileVersion -ne $peVersion) {
            throw "version_check: VERSION.txt ($fileVersion) != PE ($peVersion)"
        }
    }

    if ($ExpectedVersion -and -not $peVersion.StartsWith($ExpectedVersion)) {
        throw "version_check: expected $ExpectedVersion got $peVersion"
    }

    return $peVersion
}
