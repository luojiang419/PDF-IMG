from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from pdf_image_tool.core.models import BatchResult, PdfTaskResult
from pdf_image_tool.services.pdf_extractor import extract_images_from_pdf


class ExtractionWorker(QObject):
    progress_changed = Signal(int, int)
    log_message = Signal(str)
    task_finished = Signal(object)
    batch_finished = Signal(object)
    finished = Signal()

    def __init__(self, pdf_paths: list[Path], output_root: Path) -> None:
        super().__init__()
        self.pdf_paths = pdf_paths
        self.output_root = output_root

    @Slot()
    def run(self) -> None:
        results: list[PdfTaskResult] = []
        total = len(self.pdf_paths)

        for index, pdf_path in enumerate(self.pdf_paths, start=1):
            self.progress_changed.emit(index - 1, total)
            self.log_message.emit(f"[{index}/{total}] 开始处理：{pdf_path.name}")
            result = extract_images_from_pdf(pdf_path, self.output_root, self.log_message.emit)
            results.append(result)
            self.task_finished.emit(result)
            status_message = result.error_message or f"完成，导出 {result.extracted_count} 张图片"
            self.log_message.emit(f"[{index}/{total}] {pdf_path.name} -> {status_message}")
            self.progress_changed.emit(index, total)

        self.batch_finished.emit(BatchResult(results))
        self.finished.emit()
