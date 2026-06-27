from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.app_info import BUILD_NAME, UPDATE_PLATFORM_MACOS, UPDATE_PLATFORM_WINDOWS, patch_asset_name
from pdf_image_tool.core.versioning import normalize_version


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_map(app_dir: Path) -> dict[str, dict[str, object]]:
    files: dict[str, dict[str, object]] = {}
    for path in sorted(app_dir.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(app_dir).as_posix()
        files[relative_path] = {
            "path": path,
            "sha256": hash_file(path),
            "size": path.stat().st_size,
        }
    return files


def release_version_from_dir(release_dir: Path) -> str:
    return normalize_version(release_dir.name)


def find_release_app_dir(release_dir: Path) -> Path:
    candidates = [
        release_dir / BUILD_NAME,
        release_dir / f"{BUILD_NAME}.app",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"未找到应用目录：{release_dir}")


def release_platform_from_app_dir(app_dir: Path) -> str:
    if app_dir.name.endswith(".app"):
        return UPDATE_PLATFORM_MACOS
    return UPDATE_PLATFORM_WINDOWS


def build_patch(
    *,
    from_release_dir: Path,
    to_release_dir: Path,
    output_path: Path | None = None,
) -> Path:
    from_app_dir = find_release_app_dir(from_release_dir)
    to_app_dir = find_release_app_dir(to_release_dir)
    platform_name = release_platform_from_app_dir(to_app_dir)
    if release_platform_from_app_dir(from_app_dir) != platform_name:
        raise RuntimeError("增量补丁只能在同一平台的两个发布目录之间生成。")

    from_version = release_version_from_dir(from_release_dir)
    to_version = release_version_from_dir(to_release_dir)
    from_files = file_map(from_app_dir)
    to_files = file_map(to_app_dir)

    changed_files: list[dict[str, object]] = []
    removed_files: list[str] = []

    for relative_path, metadata in to_files.items():
        previous = from_files.get(relative_path)
        if previous is None or previous["sha256"] != metadata["sha256"]:
            changed_files.append(
                {
                    "path": relative_path,
                    "size": metadata["size"],
                    "sha256": metadata["sha256"],
                }
            )

    for relative_path in from_files:
        if relative_path not in to_files:
            removed_files.append(relative_path)

    manifest = {
        "build_name": BUILD_NAME,
        "platform": platform_name,
        "app_root_name": to_app_dir.name,
        "from_version": from_version,
        "to_version": to_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": changed_files,
        "removed_files": sorted(removed_files),
    }

    target_path = output_path or (to_release_dir / patch_asset_name(from_version, to_version, platform_name))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()

    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("patch_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for file_entry in changed_files:
            relative_path = str(file_entry["path"])
            archive.write(to_app_dir / Path(relative_path), f"payload/{relative_path}")

    return target_path


def main() -> int:
    parser = argparse.ArgumentParser(description="对比两个发布目录并生成增量补丁包。")
    parser.add_argument("--from-release", required=True, help="旧版本发布目录，例如 dist\\v0.1.19")
    parser.add_argument("--to-release", required=True, help="新版本发布目录，例如 dist\\v0.1.20")
    parser.add_argument("--output", help="输出 zip 路径，默认输出到新版本目录")
    args = parser.parse_args()

    output_path = Path(args.output).resolve() if args.output else None
    patch_path = build_patch(
        from_release_dir=Path(args.from_release).resolve(),
        to_release_dir=Path(args.to_release).resolve(),
        output_path=output_path,
    )
    print(patch_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
