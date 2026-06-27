param(
    [Parameter(Mandatory = $true)]
    [int]$WaitPid,

    [Parameter(Mandatory = $true)]
    [string]$AppExePath,

    [Parameter(Mandatory = $true)]
    [string]$AppDir,

    [Parameter(Mandatory = $true)]
    [string]$AssetPath,

    [Parameter(Mandatory = $true)]
    [ValidateSet("full", "patch")]
    [string]$AssetKind,

    [Parameter(Mandatory = $true)]
    [string]$CurrentVersion,

    [Parameter(Mandatory = $true)]
    [string]$TargetVersion,

    [string]$FallbackName,
    [string]$FallbackUrl,
    [string]$FallbackSha256,
    [string]$FallbackPath
)

$ErrorActionPreference = "Stop"

function Get-FileSha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Wait-ForAppExit {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )

    try {
        Wait-Process -Id $ProcessId -Timeout 90
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

function Start-App {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExecutablePath
    )

    if (-not (Test-Path -LiteralPath $ExecutablePath)) {
        throw "Application was not found after update: $ExecutablePath"
    }

    Start-Process -FilePath $ExecutablePath
}

function Download-FallbackInstaller {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,

        [Parameter(Mandatory = $true)]
        [string]$Destination,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedSha256
    )

    $destinationDir = Split-Path -Parent $Destination
    if (-not (Test-Path -LiteralPath $destinationDir)) {
        New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
    }

    $uri = [Uri]$Url
    $systemProxy = [System.Net.WebRequest]::GetSystemWebProxy()
    $proxyUri = $systemProxy.GetProxy($uri)
    $invokeArgs = @{
        Uri = $Url
        OutFile = $Destination
        UseBasicParsing = $true
    }

    if (-not $systemProxy.IsBypassed($uri) -and $proxyUri -and $proxyUri.AbsoluteUri -ne $Url) {
        $invokeArgs["Proxy"] = $proxyUri.AbsoluteUri
        $invokeArgs["ProxyUseDefaultCredentials"] = $true
    }

    Invoke-WebRequest @invokeArgs
    $actualSha256 = Get-FileSha256 -Path $Destination
    if ($actualSha256 -ne $ExpectedSha256.ToLowerInvariant()) {
        throw "Downloaded fallback installer failed SHA256 verification."
    }
}

function Invoke-FullInstaller {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InstallerPath,

        [Parameter(Mandatory = $true)]
        [string]$InstallDirectory
    )

    if (-not (Test-Path -LiteralPath $InstallerPath)) {
        throw "Installer was not found: $InstallerPath"
    }

    $arguments = @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/SP-",
        "/CURRENTUSER",
        "/CLOSEAPPLICATIONS",
        "/FORCECLOSEAPPLICATIONS",
        "/DIR=$InstallDirectory"
    )
    $process = Start-Process -FilePath $InstallerPath -ArgumentList $arguments -PassThru -Wait
    if ($process.ExitCode -ne 0) {
        throw "Silent installer failed with exit code $($process.ExitCode)"
    }
}

function Invoke-PatchUpdate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PatchZipPath,

        [Parameter(Mandatory = $true)]
        [string]$InstallDirectory,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedCurrentVersion,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedTargetVersion
    )

    if (-not (Test-Path -LiteralPath $PatchZipPath)) {
        throw "Patch package was not found: $PatchZipPath"
    }

    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("pdf-img-patch-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

    try {
        Expand-Archive -LiteralPath $PatchZipPath -DestinationPath $tempDir -Force
        $manifestPath = Join-Path $tempDir "patch_manifest.json"
        if (-not (Test-Path -LiteralPath $manifestPath)) {
            throw "Patch archive does not contain patch_manifest.json"
        }

        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.from_version -ne $ExpectedCurrentVersion) {
            throw "Patch from_version mismatch: $($manifest.from_version) -> $ExpectedCurrentVersion"
        }
        if ($manifest.to_version -ne $ExpectedTargetVersion) {
            throw "Patch to_version mismatch: $($manifest.to_version) -> $ExpectedTargetVersion"
        }

        foreach ($fileEntry in $manifest.files) {
            $relativePath = [string]$fileEntry.path
            $payloadPath = Join-Path $tempDir ("payload\" + $relativePath.Replace("/", "\"))
            if (-not (Test-Path -LiteralPath $payloadPath)) {
                throw "Patch payload is missing file: $relativePath"
            }

            $payloadSha256 = Get-FileSha256 -Path $payloadPath
            if ($payloadSha256 -ne ([string]$fileEntry.sha256).ToLowerInvariant()) {
                throw "Patch payload SHA256 mismatch: $relativePath"
            }

            $destinationPath = Join-Path $InstallDirectory $relativePath.Replace("/", "\")
            $destinationDir = Split-Path -Parent $destinationPath
            if (-not (Test-Path -LiteralPath $destinationDir)) {
                New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
            }

            Copy-Item -LiteralPath $payloadPath -Destination $destinationPath -Force
            $destinationSha256 = Get-FileSha256 -Path $destinationPath
            if ($destinationSha256 -ne ([string]$fileEntry.sha256).ToLowerInvariant()) {
                throw "Installed file SHA256 mismatch after copy: $relativePath"
            }
        }

        foreach ($relativePath in $manifest.removed_files) {
            $destinationPath = Join-Path $InstallDirectory ([string]$relativePath).Replace("/", "\")
            if (Test-Path -LiteralPath $destinationPath) {
                Remove-Item -LiteralPath $destinationPath -Force
            }
        }
    }
    finally {
        if (Test-Path -LiteralPath $tempDir) {
            Remove-Item -LiteralPath $tempDir -Recurse -Force
        }
    }
}

Wait-ForAppExit -ProcessId $WaitPid
Start-Sleep -Seconds 1

if ($AssetKind -eq "full") {
    Invoke-FullInstaller -InstallerPath $AssetPath -InstallDirectory $AppDir
    Start-App -ExecutablePath $AppExePath
    exit 0
}

try {
    Invoke-PatchUpdate `
        -PatchZipPath $AssetPath `
        -InstallDirectory $AppDir `
        -ExpectedCurrentVersion $CurrentVersion `
        -ExpectedTargetVersion $TargetVersion
    Start-App -ExecutablePath $AppExePath
    exit 0
}
catch {
    if (-not $FallbackUrl -or -not $FallbackSha256 -or -not $FallbackPath) {
        throw
    }

    Download-FallbackInstaller -Url $FallbackUrl -Destination $FallbackPath -ExpectedSha256 $FallbackSha256
    Invoke-FullInstaller -InstallerPath $FallbackPath -InstallDirectory $AppDir
    Start-App -ExecutablePath $AppExePath
    exit 0
}
