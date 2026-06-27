from __future__ import annotations

import argparse
import hashlib
import json
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
    UPDATE_REPOSITORY,
    installer_asset_name,
    manifest_asset_name,
    patch_asset_name,
    release_tag_name,
)
from pdf_image_tool.core.versioning import bump_patch_version


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


def write_release_manifest(
    *,
    release_dir: Path,
    version: str,
    repository: str,
    installer_path: Path,
    patch_path: Path | None,
    previous_version: str | None,
) -> Path:
    tag_name = release_tag_name(version)
    manifest = {
        "version": version,
        "tag_name": tag_name,
        "repository": repository,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "full": asset_metadata(installer_path, repository=repository, tag_name=tag_name),
        "patches": [],
    }
    if patch_path is not None and previous_version is not None:
        manifest["patches"].append(
            {
                "from_version": previous_version,
                "to_version": version,
                **asset_metadata(patch_path, repository=repository, tag_name=tag_name),
            }
        )

    manifest_path = release_dir / manifest_asset_name(version)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def ensure_github_release(repository: str, tag_name: str, asset_paths: list[Path]) -> None:
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
            *files,
        ]
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="自动递增版本、构建产物并上传 GitHub Release。")
    parser.add_argument("--repository", default=UPDATE_REPOSITORY, help="GitHub 仓库，格式 owner/repo")
    args = parser.parse_args()

    original_text = APP_INFO_PATH.read_text(encoding="utf-8")
    current_version = APP_VERSION
    next_version = bump_patch_version(current_version)
    previous_release_dir = ROOT / "dist" / release_tag_name(current_version)
    installer_path = ROOT / "dist" / release_tag_name(next_version) / installer_asset_name(next_version)
    patch_path: Path | None = None
    manifest_path: Path | None = None
    success = False

    try:
        APP_INFO_PATH.write_text(replace_app_version(original_text, next_version), encoding="utf-8")

        release_dir_text = run_command([sys.executable, str(ROOT / "scripts" / "build_release.py")])
        release_dir = Path(release_dir_text).resolve()
        if release_dir.name != release_tag_name(next_version):
            raise RuntimeError(f"构建目录版本不匹配：{release_dir.name}")

        run_command(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "scripts" / "build_installer.ps1"),
                "-ReleaseDir",
                str(release_dir),
            ]
        )

        if not installer_path.exists():
            raise FileNotFoundError(f"未找到安装包：{installer_path}")

        if previous_release_dir.exists():
            patch_text = run_command(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "build_delta_update.py"),
                    "--from-release",
                    str(previous_release_dir),
                    "--to-release",
                    str(release_dir),
                ]
            )
            patch_path = Path(patch_text).resolve()
            expected_patch_name = patch_asset_name(current_version, next_version)
            if patch_path.name != expected_patch_name:
                raise RuntimeError(f"补丁包命名不匹配：{patch_path.name}")

        manifest_path = write_release_manifest(
            release_dir=release_dir,
            version=next_version,
            repository=args.repository,
            installer_path=installer_path,
            patch_path=patch_path,
            previous_version=current_version if patch_path is not None else None,
        )

        asset_paths = [installer_path]
        if patch_path is not None:
            asset_paths.append(patch_path)
        asset_paths.append(manifest_path)
        ensure_github_release(args.repository, release_tag_name(next_version), asset_paths)
        success = True
        print(json.dumps(
            {
                "repository": args.repository,
                "version": next_version,
                "release_dir": str(release_dir),
                "assets": [path.name for path in asset_paths],
                "build_name": BUILD_NAME,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 0
    finally:
        if not success:
            APP_INFO_PATH.write_text(original_text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
