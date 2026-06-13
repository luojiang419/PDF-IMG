from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QUrl


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.ui.main_window import collect_pdf_paths_from_directory, extract_local_pdf_paths


class DragDropHelpersTests(unittest.TestCase):
    def test_extract_local_pdf_paths_filters_non_pdf_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_file = temp_path / "sample.pdf"
            txt_file = temp_path / "notes.txt"
            upper_pdf_file = temp_path / "SECOND.PDF"
            pdf_file.write_text("pdf", encoding="utf-8")
            txt_file.write_text("txt", encoding="utf-8")
            upper_pdf_file.write_text("pdf", encoding="utf-8")

            urls = [
                QUrl.fromLocalFile(str(pdf_file)),
                QUrl.fromLocalFile(str(txt_file)),
                QUrl.fromLocalFile(str(pdf_file)),
                QUrl.fromLocalFile(str(upper_pdf_file)),
                QUrl("https://example.com/test.pdf"),
            ]

            paths = extract_local_pdf_paths(urls)

            self.assertEqual(paths, [pdf_file.resolve(), upper_pdf_file.resolve()])

    def test_extract_local_pdf_paths_collects_pdfs_from_directories_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            folder = temp_path / "drop-folder"
            nested = folder / "nested"
            folder.mkdir()
            nested.mkdir()
            root_pdf = folder / "a.pdf"
            nested_pdf = nested / "b.PDF"
            ignored = nested / "c.txt"
            root_pdf.write_text("pdf", encoding="utf-8")
            nested_pdf.write_text("pdf", encoding="utf-8")
            ignored.write_text("txt", encoding="utf-8")

            paths = extract_local_pdf_paths([QUrl.fromLocalFile(str(folder))])

            self.assertEqual(paths, [root_pdf.resolve(), nested_pdf.resolve()])

    def test_collect_pdf_paths_from_directory_returns_sorted_recursive_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            nested = temp_path / "nested"
            nested.mkdir()
            late_pdf = temp_path / "z.pdf"
            early_pdf = nested / "a.pdf"
            late_pdf.write_text("pdf", encoding="utf-8")
            early_pdf.write_text("pdf", encoding="utf-8")

            paths = collect_pdf_paths_from_directory(temp_path)

            self.assertEqual(paths, [early_pdf.resolve(), late_pdf.resolve()])


if __name__ == "__main__":
    unittest.main()
