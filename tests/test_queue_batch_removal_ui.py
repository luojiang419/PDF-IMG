from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.ui.main_window import MainWindow


APP = QApplication.instance() or QApplication([])


class QueueBatchRemovalTests(unittest.TestCase):
    def create_pdf_placeholder(self, path: Path) -> None:
        path.write_text("pdf", encoding="utf-8")

    def test_remove_selected_source_batch_only_removes_that_import_batch(self) -> None:
        window = MainWindow("批量移除测试")
        window.show()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                first_batch_a = temp_path / "a.pdf"
                first_batch_b = temp_path / "b.pdf"
                second_batch = temp_path / "c.pdf"
                for file_path in [first_batch_a, first_batch_b, second_batch]:
                    self.create_pdf_placeholder(file_path)

                window.add_pdf_paths([first_batch_a, first_batch_b], source="文件夹选择（测试）")
                window.add_pdf_paths([second_batch], source="文件夹选择（测试）")
                APP.processEvents()

                window.file_list.item(0).setSelected(True)
                APP.processEvents()
                window.remove_selected_source_batches()
                APP.processEvents()

                remaining_names = [window.file_list.item(index).text() for index in range(window.file_list.count())]
                self.assertEqual(remaining_names, ["c.pdf"])
                self.assertEqual(len(window.pdf_paths), 1)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
