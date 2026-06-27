from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.app_info import APP_VERSION
from pdf_image_tool.ui.main_window import MainWindow


APP = QApplication.instance() or QApplication([])


class UpdateUiTests(unittest.TestCase):
    def test_settings_tab_exposes_update_controls_and_button_signal(self) -> None:
        window = MainWindow("更新 UI 测试", current_version=APP_VERSION)
        requests: list[str] = []
        window.manual_update_check_requested.connect(lambda: requests.append("clicked"))
        window.show()
        APP.processEvents()

        try:
            window.tabs.setCurrentIndex(3)
            APP.processEvents()
            self.assertEqual(window.check_update_button.text(), "检查更新")
            self.assertEqual(window.current_version_label.text(), f"当前版本：v{APP_VERSION}")
            self.assertTrue(window.update_status_label.wordWrap())
            QTest.mouseClick(window.check_update_button, Qt.LeftButton)
            APP.processEvents()
            self.assertEqual(requests, ["clicked"])

            window.set_update_busy(True)
            self.assertFalse(window.check_update_button.isEnabled())
            window.set_update_busy(False)
            self.assertTrue(window.check_update_button.isEnabled())
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
