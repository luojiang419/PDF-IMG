from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QScrollArea, QTabWidget


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.ui.main_window import MainWindow


APP = QApplication.instance() or QApplication([])


class MainWindowLayoutTests(unittest.TestCase):
    def test_main_window_uses_fixed_tab_layout_without_page_scroll(self) -> None:
        window = MainWindow("布局测试")
        window.resize(window.minimumSize())
        window.show()
        APP.processEvents()

        try:
            self.assertNotIsInstance(window.centralWidget(), QScrollArea)
            self.assertIsInstance(window.tabs, QTabWidget)
            self.assertEqual(
                [window.tabs.tabText(index) for index in range(window.tabs.count())],
                ["快速提取", "进阶操作", "运行日志", "设置"],
            )

            window.tabs.setCurrentIndex(0)
            APP.processEvents()
            self.assertGreaterEqual(window.quick_file_list.height(), 180)

            window.tabs.setCurrentIndex(1)
            APP.processEvents()
            self.assertGreaterEqual(window.file_list.height(), 160)
            self.assertGreaterEqual(window.result_table.height(), 100)
            self.assertGreaterEqual(window.preview_image_label.height(), 80)
            preview_y = window.preview_image_label.mapTo(window, QPoint(0, 0)).y()
            result_y = window.result_table.mapTo(window, QPoint(0, 0)).y()
            self.assertLess(preview_y, result_y)

            window.tabs.setCurrentIndex(2)
            APP.processEvents()
            self.assertGreaterEqual(window.log_output.height(), 300)

            window.tabs.setCurrentIndex(3)
            APP.processEvents()
            self.assertTrue(window.output_line_edit.isVisible())
            self.assertFalse(hasattr(window, "stat_total_files"))

            self.assertTrue(window.queue_drop_hint_label.wordWrap())
            self.assertTrue(window.action_hint_label.wordWrap())
            self.assertTrue(window.result_hint_label.wordWrap())
            self.assertTrue(window.preview_hint_label.wordWrap())
            self.assertTrue(window.preview_meta_label.wordWrap())
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
