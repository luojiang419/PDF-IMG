from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableWidgetItem


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.ui.main_window import FullscreenPreviewDialog, MainWindow


APP = QApplication.instance() or QApplication([])


class PreviewNavigationShortcutTests(unittest.TestCase):
    def create_image(self, path: Path, color_name: str) -> None:
        image = QImage(64, 64, QImage.Format_RGB32)
        image.fill(QColor(color_name))
        image.save(str(path))

    def test_left_right_keys_switch_preview_images(self) -> None:
        window = MainWindow("快捷键预览测试")
        window.show()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                self.create_image(temp_path / "page-001_img-001.png", "red")
                self.create_image(temp_path / "page-001_img-002.png", "green")
                self.create_image(temp_path / "page-001_img-003.png", "blue")

                window.result_table.setRowCount(1)
                first_item = QTableWidgetItem("sample.pdf")
                first_item.setData(Qt.UserRole, temp_path.as_posix())
                window.result_table.setItem(0, 0, first_item)
                for column in range(1, 5):
                    window.result_table.setItem(0, column, QTableWidgetItem("0"))

                window.result_table.setFocus()
                window.result_table.selectRow(0)
                APP.processEvents()
                self.assertEqual(window.preview_position_label.text(), "1 / 3")

                QTest.keyClick(window.result_table, Qt.Key_Right)
                APP.processEvents()
                self.assertEqual(window.preview_position_label.text(), "2 / 3")

                QTest.keyClick(window.result_table, Qt.Key_Right)
                APP.processEvents()
                self.assertEqual(window.preview_position_label.text(), "3 / 3")

                QTest.keyClick(window.result_table, Qt.Key_Left)
                APP.processEvents()
                self.assertEqual(window.preview_position_label.text(), "2 / 3")
        finally:
            window.close()

    def test_home_end_keys_jump_to_first_and_last_preview_images(self) -> None:
        window = MainWindow("首尾快捷键预览测试")
        window.show()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                self.create_image(temp_path / "page-001_img-001.png", "red")
                self.create_image(temp_path / "page-001_img-002.png", "green")
                self.create_image(temp_path / "page-001_img-003.png", "blue")

                window.result_table.setRowCount(1)
                first_item = QTableWidgetItem("sample.pdf")
                first_item.setData(Qt.UserRole, temp_path.as_posix())
                window.result_table.setItem(0, 0, first_item)
                for column in range(1, 5):
                    window.result_table.setItem(0, column, QTableWidgetItem("0"))

                window.result_table.setFocus()
                window.result_table.selectRow(0)
                APP.processEvents()
                self.assertEqual(window.preview_position_label.text(), "1 / 3")

                QTest.keyClick(window.result_table, Qt.Key_End)
                APP.processEvents()
                self.assertEqual(window.preview_position_label.text(), "3 / 3")

                QTest.keyClick(window.result_table, Qt.Key_Home)
                APP.processEvents()
                self.assertEqual(window.preview_position_label.text(), "1 / 3")
        finally:
            window.close()

    def test_copy_button_copies_current_preview_image_to_clipboard(self) -> None:
        window = MainWindow("复制预览测试")
        window.show()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                self.create_image(temp_path / "page-001_img-001.png", "red")

                window.result_table.setRowCount(1)
                first_item = QTableWidgetItem("sample.pdf")
                first_item.setData(Qt.UserRole, temp_path.as_posix())
                window.result_table.setItem(0, 0, first_item)
                for column in range(1, 5):
                    window.result_table.setItem(0, column, QTableWidgetItem("0"))

                window.result_table.selectRow(0)
                APP.processEvents()
                self.assertTrue(window.preview_copy_button.isEnabled())
                self.assertTrue(window.preview_fullscreen_button.isEnabled())

                window.copy_current_preview_image()
                clipboard_pixmap = APP.clipboard().pixmap()
                self.assertFalse(clipboard_pixmap.isNull())
                self.assertEqual(clipboard_pixmap.width(), 64)
                self.assertEqual(clipboard_pixmap.height(), 64)
        finally:
            window.close()

    def test_clicking_preview_image_opens_fullscreen_preview(self) -> None:
        window = MainWindow("点击预览全屏测试")
        window.show()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                self.create_image(temp_path / "page-001_img-001.png", "red")

                window.result_table.setRowCount(1)
                first_item = QTableWidgetItem("sample.pdf")
                first_item.setData(Qt.UserRole, temp_path.as_posix())
                window.result_table.setItem(0, 0, first_item)
                for column in range(1, 5):
                    window.result_table.setItem(0, column, QTableWidgetItem("0"))

                window.result_table.selectRow(0)
                APP.processEvents()
                QTest.mouseClick(window.preview_image_label, Qt.LeftButton)
                APP.processEvents()

                self.assertIsNotNone(window.fullscreen_preview_dialog)
                self.assertTrue(window.fullscreen_preview_dialog.isVisible())
                screen = window.screen() or APP.primaryScreen()
                if screen is not None:
                    self.assertEqual(window.fullscreen_preview_dialog.geometry(), screen.availableGeometry())
                window.fullscreen_preview_dialog.close()
        finally:
            window.close()

    def test_fullscreen_preview_switches_copies_and_closes_with_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            image_paths = [
                temp_path / "page-001_img-001.png",
                temp_path / "page-001_img-002.png",
                temp_path / "page-001_img-003.png",
            ]
            for image_path, color_name in zip(image_paths, ["red", "green", "blue"]):
                self.create_image(image_path, color_name)

            changed_indexes: list[int] = []
            dialog = FullscreenPreviewDialog(image_paths, 0)
            dialog.preview_index_changed.connect(changed_indexes.append)
            dialog.show()
            APP.processEvents()
            try:
                dialog.setFocus()
                QTest.keyClick(dialog, Qt.Key_Right)
                APP.processEvents()
                self.assertEqual(dialog.preview_index, 1)
                self.assertEqual(changed_indexes, [1])

                QTest.keyClick(dialog, Qt.Key_Left)
                APP.processEvents()
                self.assertEqual(dialog.preview_index, 0)
                self.assertEqual(changed_indexes, [1, 0])

                dialog.fullscreen_next_button.setFocus()
                QTest.keyClick(dialog.fullscreen_next_button, Qt.Key_Right)
                APP.processEvents()
                self.assertEqual(dialog.preview_index, 1)
                self.assertEqual(changed_indexes, [1, 0, 1])

                dialog.copy_current_image_to_clipboard()
                clipboard_pixmap = APP.clipboard().pixmap()
                self.assertFalse(clipboard_pixmap.isNull())
                self.assertEqual(clipboard_pixmap.width(), 64)
                self.assertEqual(clipboard_pixmap.height(), 64)

                QTest.keyClick(dialog, Qt.Key_Escape)
                APP.processEvents()
                self.assertFalse(dialog.isVisible())
            finally:
                dialog.close()


if __name__ == "__main__":
    unittest.main()
