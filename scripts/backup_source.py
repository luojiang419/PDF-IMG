from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.versioning import next_index_name


EXCLUDED_NAMES = {
    "backup",
    "dist",
    "进度快照",
    "build",
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
}


def copy_entry(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )
    else:
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="备份当前项目源码。")
    parser.add_argument("--stage", required=True, help="阶段名称，例如：项目骨架")
    args = parser.parse_args()

    backup_root = ROOT / "backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    existing_names = [item.name for item in backup_root.iterdir()]
    backup_name = next_index_name(existing_names, args.stage)
    target_dir = backup_root / backup_name
    target_dir.mkdir(parents=True, exist_ok=False)

    for entry in ROOT.iterdir():
        if entry.name in EXCLUDED_NAMES:
            continue
        copy_entry(entry, target_dir / entry.name)

    print(target_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
