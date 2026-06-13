from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class PdfTaskResult:
    pdf_path: Path
    output_dir: Path | None = None
    extracted_count: int = 0
    converted_count: int = 0
    skipped_count: int = 0
    page_count: int = 0
    status: str = "pending"
    error_message: str | None = None
    log_lines: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return self.error_message is None and self.status in {"success", "no_images"}

    @property
    def status_label(self) -> str:
        mapping = {
            "success": "完成",
            "no_images": "无图片",
            "failed": "失败",
            "partial": "部分完成",
        }
        return mapping.get(self.status, self.status)


@dataclass(slots=True)
class BatchResult:
    items: list[PdfTaskResult]

    @property
    def total_files(self) -> int:
        return len(self.items)

    @property
    def success_files(self) -> int:
        return sum(1 for item in self.items if item.is_success)

    @property
    def failed_files(self) -> int:
        return sum(1 for item in self.items if item.error_message)

    @property
    def total_images(self) -> int:
        return sum(item.extracted_count for item in self.items)

    @property
    def total_converted(self) -> int:
        return sum(item.converted_count for item in self.items)

    @property
    def total_skipped(self) -> int:
        return sum(item.skipped_count for item in self.items)
