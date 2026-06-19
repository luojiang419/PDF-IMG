from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.app_info import BUILD_NAME
from pdf_image_tool.core.versioning import VERSION_PATTERN


def latest_release_dir(dist_root: Path) -> Path:
    candidates = []
    for item in dist_root.iterdir():
        if item.is_dir() and VERSION_PATTERN.match(item.name):
            candidates.append(item)
    if not candidates:
        raise RuntimeError("dist 目录下没有可用的版本目录。")
    return sorted(candidates, key=lambda path: tuple(int(part) for part in path.name[1:].split(".")))[-1]


def build_dmg(release_root: Path) -> Path:
    if platform.system() != "Darwin":
        raise RuntimeError("DMG 只能在 macOS 上构建。")

    app_path = release_root / f"{BUILD_NAME}.app"
    if not app_path.exists():
        raise RuntimeError(f"未找到 macOS app：{app_path}")

    arch = platform.machine() or "mac"
    dmg_name = f"{BUILD_NAME}-{release_root.name}-mac-{arch}.dmg"
    dmg_path = release_root / dmg_name
    staging_root = ROOT / "build" / "dmg-staging" / release_root.name

    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)
    if dmg_path.exists():
        dmg_path.unlink()

    shutil.copytree(app_path, staging_root / app_path.name, symlinks=True)
    (staging_root / "Applications").symlink_to("/Applications", target_is_directory=True)

    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            f"{BUILD_NAME} {release_root.name}",
            "-srcfolder",
            str(staging_root),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ],
        check=True,
    )
    shutil.rmtree(staging_root)
    print(dmg_path)
    return dmg_path


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 macOS DMG 安装包。")
    parser.add_argument(
        "--release-root",
        type=Path,
        default=None,
        help="版本目录，例如 dist/v0.1.19；不传则使用 dist 下最新版本目录。",
    )
    args = parser.parse_args()

    release_root = args.release_root or latest_release_dir(ROOT / "dist")
    build_dmg(release_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
