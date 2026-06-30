import sys


APP_NAME = "PDF 图片提取工具"
BUILD_NAME = "PDF-IMG-Extractor"
APP_VERSION = "0.1.24"
APP_ICON_PARTS = ("logo", "logo 拷贝.png")

UPDATE_REPOSITORY_OWNER = "luojiang419"
UPDATE_REPOSITORY_NAME = "PDF-IMG"
UPDATE_REPOSITORY = f"{UPDATE_REPOSITORY_OWNER}/{UPDATE_REPOSITORY_NAME}"
INSTALL_DIR_NAME = "PDF-IMG Extractor"
UPDATE_PLATFORM_WINDOWS = "windows"
UPDATE_PLATFORM_MACOS = "macos"
UPDATE_PLATFORM_LINUX = "linux"


def release_tag_name(version: str) -> str:
    return f"v{version}"


def normalize_update_platform(platform_name: str) -> str:
    cleaned = platform_name.strip().lower().replace("-", "").replace("_", "")
    if cleaned in {"win", "win32", "windows", "cygwin"}:
        return UPDATE_PLATFORM_WINDOWS
    if cleaned in {"darwin", "mac", "macos", "osx"}:
        return UPDATE_PLATFORM_MACOS
    if cleaned in {"linux", "linux2"}:
        return UPDATE_PLATFORM_LINUX
    return platform_name.strip().lower()


def current_update_platform(platform_name: str | None = None) -> str:
    raw_platform = sys.platform if platform_name is None else platform_name
    return normalize_update_platform(raw_platform)


def update_platform_label(platform_name: str | None = None) -> str:
    normalized = current_update_platform(platform_name)
    if normalized == UPDATE_PLATFORM_WINDOWS:
        return "Windows"
    if normalized == UPDATE_PLATFORM_MACOS:
        return "macOS"
    if normalized == UPDATE_PLATFORM_LINUX:
        return "Linux"
    return normalized


def installer_asset_name(version: str) -> str:
    return f"{BUILD_NAME}-{release_tag_name(version)}-Setup.exe"


def macos_dmg_asset_name(version: str, arch: str) -> str:
    return f"{BUILD_NAME}-{release_tag_name(version)}-mac-{arch}.dmg"


def legacy_manifest_asset_name(version: str) -> str:
    return f"{BUILD_NAME}-{release_tag_name(version)}-manifest.json"


def manifest_asset_name(version: str, platform_name: str | None = None) -> str:
    platform_key = current_update_platform(platform_name)
    return f"{BUILD_NAME}-{release_tag_name(version)}-{platform_key}-manifest.json"


def manifest_asset_candidates(version: str, platform_name: str | None = None) -> tuple[str, ...]:
    platform_key = current_update_platform(platform_name)
    return (
        manifest_asset_name(version, platform_key),
        legacy_manifest_asset_name(version),
    )


def patch_asset_name(from_version: str, to_version: str, platform_name: str | None = None) -> str:
    platform_key = current_update_platform(platform_name)
    return f"{BUILD_NAME}-{release_tag_name(from_version)}-to-{release_tag_name(to_version)}-{platform_key}-patch.zip"
