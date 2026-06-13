from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.versioning import next_index_name


def build_markdown(
    *,
    title: str,
    completed: list[str],
    current_module: str,
    todo: list[str],
    next_step: str,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 已完成内容",
    ]
    lines.extend(f"- {item}" for item in completed)
    lines.extend(
        [
            "",
            "## 当前修改模块",
            f"- {current_module}",
            "",
            "## 待办清单（未完成）",
        ]
    )
    lines.extend(f"- {item}" for item in todo)
    lines.extend(
        [
            "",
            "## 下一步要做什么",
            f"- {next_step}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成项目进度快照。")
    parser.add_argument("--title", required=True, help="快照标题")
    parser.add_argument("--current-module", required=True, help="当前修改到哪个模块")
    parser.add_argument("--next-step", required=True, help="下一步要做什么")
    parser.add_argument("--completed", action="append", required=True, help="已完成内容，可重复传入")
    parser.add_argument("--todo", action="append", required=True, help="待办事项，可重复传入")
    args = parser.parse_args()

    snapshot_root = ROOT / "进度快照"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    existing_names = [item.name for item in snapshot_root.iterdir()]
    file_name = next_index_name(existing_names, args.title) + ".md"
    target_path = snapshot_root / file_name

    markdown = build_markdown(
        title=args.title,
        completed=args.completed,
        current_module=args.current_module,
        todo=args.todo,
        next_step=args.next_step,
    )
    target_path.write_text(markdown, encoding="utf-8")
    print(target_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
