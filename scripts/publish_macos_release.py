from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.app_info import (
    APP_VERSION,
    BUILD_NAME,
    UPDATE_PLATFORM_MACOS,
    UPDATE_REPOSITORY,
    legacy_manifest_asset_name,
    macos_dmg_asset_name,
    manifest_asset_name,
    release_tag_name,
)


APP_INFO_PATH = ROOT / "src" / "pdf_image_tool" / "core" / "app_info.py"
VERSION_PATTERN = re.compile(r'^APP_VERSION = "(?P<version>\d+\.\d+\.\d+)"$', re.MULTILINE)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_app_version(source_text: str, version: str) -> str:
    replaced_text, count = VERSION_PATTERN.subn(f'APP_VERSION = "{version}"', source_text, count=1)
    if count != 1:
        raise RuntimeError("未能在 app_info.py 中定位 APP_VERSION。")
    return replaced_text


def run_command(command: list[str], *, cwd: Path = ROOT) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    stdout = completed.stdout.strip()
    if stdout:
        return stdout.splitlines()[-1].strip()
    return ""


def asset_url(repository: str, tag_name: str, file_name: str) -> str:
    return f"https://github.com/{repository}/releases/download/{tag_name}/{quote(file_name)}"


def asset_metadata(path: Path, *, repository: str, tag_name: str) -> dict[str, object]:
    return {
        "name": path.name,
        "size": path.stat().st_size,
        "sha256": hash_file(path),
        "url": asset_url(repository, tag_name, path.name),
    }


def write_release_manifests(
    *,
    release_dir: Path,
    version: str,
    repository: str,
    dmg_path: Path,
    include_legacy_manifest: bool,
) -> list[Path]:
    tag_name = release_tag_name(version)
    manifest = {
        "version": version,
        "tag_name": tag_name,
        "repository": repository,
        "platform": UPDATE_PLATFORM_MACOS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "full": asset_metadata(dmg_path, repository=repository, tag_name=tag_name),
        "patches": [],
    }

    manifest_names = [manifest_asset_name(version, UPDATE_PLATFORM_MACOS)]
    if include_legacy_manifest:
        manifest_names.append(legacy_manifest_asset_name(version))

    manifest_paths: list[Path] = []
    for manifest_name in manifest_names:
        manifest_path = release_dir / manifest_name
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest_paths.append(manifest_path)
    return manifest_paths


def ensure_github_release(repository: str, tag_name: str, asset_paths: list[Path], *, target: str) -> None:
    view_result = subprocess.run(
        ["gh", "release", "view", tag_name, "--repo", repository],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    files = [str(path) for path in asset_paths]
    if view_result.returncode == 0:
        command = ["gh", "release", "upload", tag_name, "--repo", repository, "--clobber", *files]
    else:
        command = [
            "gh",
            "release",
            "create",
            tag_name,
            "--repo",
            repository,
            "--title",
            tag_name,
            "--latest",
            "--target",
            target,
            *files,
        ]
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="构建并上传 macOS DMG GitHub Release。")
    parser.add_argument("--repository", default=UPDATE_REPOSITORY, help="GitHub 仓库，格式 owner/repo")
    parser.add_argument("--version", default=APP_VERSION, help="要发布的版本号，例如 0.1.23")
    parser.add_argument(
        "--no-legacy-manifest",
        action="store_true",
        help="不上传旧命名 manifest；默认会上传以兼容旧版客户端。",
    )
    args = parser.parse_args()

    if platform.system() != "Darwin":
        raise RuntimeError("macOS Release 只能在 macOS 上构建。")

    target_version = args.version
    tag_name = release_tag_name(target_version)
    original_text = APP_INFO_PATH.read_text(encoding="utf-8")
    success = False

    try:
        if target_version != APP_VERSION:
            APP_INFO_PATH.write_text(replace_app_version(original_text, target_version), encoding="utf-8")

        release_dir_text = run_command([sys.executable, str(ROOT / "scripts" / "build_release.py")])
        release_dir = Path(release_dir_text).resolve()
        if release_dir.name != tag_name:
            raise RuntimeError(f"构建目录版本不匹配：{release_dir.name}")

        dmg_text = run_command(
            [
                sys.executable,
                str(ROOT / "scripts" / "build_dmg.py"),
                "--release-root",
                str(release_dir),
            ]
        )
        dmg_path = Path(dmg_text).resolve()
        expected_dmg_name = macos_dmg_asset_name(target_version, platform.machine() or "mac")
        if dmg_path.name != expected_dmg_name:
            raise RuntimeError(f"DMG 命名不匹配：{dmg_path.name}")

        manifest_paths = write_release_manifests(
            release_dir=release_dir,
            version=target_version,
            repository=args.repository,
            dmg_path=dmg_path,
            include_legacy_manifest=not args.no_legacy_manifest,
        )
        asset_paths = [dmg_path, *manifest_paths]
        target_commit = run_command(["git", "rev-parse", "HEAD"])
        ensure_github_release(args.repository, tag_name, asset_paths, target=target_commit)
        success = True
        print(
            json.dumps(
                {
                    "repository": args.repository,
                    "version": target_version,
                    "release_dir": str(release_dir),
                    "assets": [path.name for path in asset_paths],
                    "build_name": BUILD_NAME,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        if not success and target_version != APP_VERSION:
            APP_INFO_PATH.write_text(original_text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
