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

from pdf_image_tool.app import load_stylesheet
from pdf_image_tool.ui.main_window import MainWindow


APP = QApplication.instance() or QApplication([])


class ThemeToggleUiTests(unittest.TestCase):
    def test_theme_toggle_button_switches_between_dark_and_light(self) -> None:
        original_stylesheet = APP.styleSheet()
        dark_stylesheet = load_stylesheet("dark")
        light_stylesheet = load_stylesheet("light")
        window = MainWindow("主题切换测试", initial_theme_name="dark")

        def apply_theme(theme_name: str) -> None:
            APP.setStyleSheet(load_stylesheet(theme_name))
            window.set_theme(theme_name)

        window.theme_change_requested.connect(apply_theme)
        apply_theme("dark")
        window.show()
        APP.processEvents()

        try:
            self.assertNotEqual(dark_stylesheet, light_stylesheet)
            self.assertEqual(window.current_theme_name, "dark")
            self.assertFalse(window.theme_toggle_button.icon().isNull())
            self.assertEqual(window.theme_toggle_button.toolTip(), "切换到浅色主题")
            self.assertEqual(APP.styleSheet(), dark_stylesheet)

            QTest.mouseClick(window.theme_toggle_button, Qt.LeftButton)
            APP.processEvents()
            self.assertEqual(window.current_theme_name, "light")
            self.assertEqual(window.theme_toggle_button.toolTip(), "切换到深色主题")
            self.assertEqual(APP.styleSheet(), light_stylesheet)

            QTest.mouseClick(window.theme_toggle_button, Qt.LeftButton)
            APP.processEvents()
            self.assertEqual(window.current_theme_name, "dark")
            self.assertEqual(window.theme_toggle_button.toolTip(), "切换到浅色主题")
            self.assertEqual(APP.styleSheet(), dark_stylesheet)
        finally:
            window.close()
            APP.setStyleSheet(original_stylesheet)


if __name__ == "__main__":
    unittest.main()
