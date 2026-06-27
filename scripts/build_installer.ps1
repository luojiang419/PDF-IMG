param(
    [string]$ReleaseDir
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$DistRoot = Join-Path $Root "dist"
$BuildName = "PDF-IMG-Extractor"
$AppName = "PDF IMG Extractor"
$InstallDirName = "PDF-IMG Extractor"

function Find-Iscc {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    throw "ISCC.exe was not found. Please install Inno Setup 6 first."
}

function Get-LatestReleaseDir {
    if (-not (Test-Path -LiteralPath $DistRoot)) {
        throw "dist directory was not found. Run python scripts\build_release.py first."
    }

    $release = Get-ChildItem -LiteralPath $DistRoot -Directory |
        Where-Object { $_.Name -match '^v\d+\.\d+\.\d+$' } |
        Sort-Object @{ Expression = { [version]($_.Name.Substring(1)) } } |
        Select-Object -Last 1

    if (-not $release) {
        throw "No vX.Y.Z release directory was found in dist."
    }

    return $release.FullName
}

if (-not $ReleaseDir) {
    $ReleaseDir = Get-LatestReleaseDir
}

$ResolvedReleaseDir = (Resolve-Path -LiteralPath $ReleaseDir).Path
$ReleaseName = Split-Path -Leaf $ResolvedReleaseDir
$Version = $ReleaseName.TrimStart("v")
$AppDir = Join-Path $ResolvedReleaseDir $BuildName
$IconFile = Join-Path $Root "build\generated\app_icon.ico"
$InstallerBaseName = "$BuildName-$ReleaseName-Setup"
$InstallerPath = Join-Path $ResolvedReleaseDir "$InstallerBaseName.exe"
$IssPath = Join-Path $PSScriptRoot "installer.iss"

if (-not (Test-Path -LiteralPath $AppDir)) {
    throw "Application directory was not found: $AppDir"
}

if (-not (Test-Path -LiteralPath (Join-Path $AppDir "$BuildName.exe"))) {
    throw "Application executable was not found: $(Join-Path $AppDir "$BuildName.exe")"
}

if (-not (Test-Path -LiteralPath $IconFile)) {
    throw "Installer icon was not found: $IconFile. Run python scripts\build_release.py first."
}

$env:PDF_IMG_APP_NAME = $AppName
$env:PDF_IMG_APP_VERSION = $Version
$env:PDF_IMG_BUILD_NAME = $BuildName
$env:PDF_IMG_SOURCE_DIR = $AppDir
$env:PDF_IMG_OUTPUT_DIR = $ResolvedReleaseDir
$env:PDF_IMG_OUTPUT_BASE = $InstallerBaseName
$env:PDF_IMG_ICON_FILE = $IconFile
$env:PDF_IMG_INSTALL_DIR_NAME = $InstallDirName

$Iscc = Find-Iscc
& $Iscc $IssPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (-not (Test-Path -LiteralPath $InstallerPath)) {
    throw "Installer was not generated: $InstallerPath"
}

Write-Output $InstallerPath
