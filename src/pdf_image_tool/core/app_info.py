APP_NAME = "PDF 图片提取工具"
BUILD_NAME = "PDF-IMG-Extractor"
APP_VERSION = "0.1.20"
APP_ICON_PARTS = ("logo", "logo 拷贝.png")

UPDATE_REPOSITORY_OWNER = "luojiang419"
UPDATE_REPOSITORY_NAME = "PDF-IMG"
UPDATE_REPOSITORY = f"{UPDATE_REPOSITORY_OWNER}/{UPDATE_REPOSITORY_NAME}"
INSTALL_DIR_NAME = "PDF-IMG Extractor"


def release_tag_name(version: str) -> str:
    return f"v{version}"


def installer_asset_name(version: str) -> str:
    return f"{BUILD_NAME}-{release_tag_name(version)}-Setup.exe"


def manifest_asset_name(version: str) -> str:
    return f"{BUILD_NAME}-{release_tag_name(version)}-manifest.json"


def patch_asset_name(from_version: str, to_version: str) -> str:
    return f"{BUILD_NAME}-{release_tag_name(from_version)}-to-{release_tag_name(to_version)}-patch.zip"
