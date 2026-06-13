from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.preview import find_preview_image, list_preview_images


class PreviewHelpersTests(unittest.TestCase):
    def test_list_preview_images_returns_sorted_supported_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "z-last.png").write_bytes(b"png")
            (temp_path / "a-first.txt").write_text("ignore", encoding="utf-8")
            (temp_path / "b-preview.JPG").write_bytes(b"jpg")

            preview_paths = list_preview_images(temp_path)

            self.assertEqual(preview_paths, [temp_path / "b-preview.JPG", temp_path / "z-last.png"])

    def test_find_preview_image_returns_first_supported_file_in_name_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "z-last.png").write_bytes(b"png")
            (temp_path / "a-first.txt").write_text("ignore", encoding="utf-8")
            (temp_path / "b-preview.JPG").write_bytes(b"jpg")

            preview_path = find_preview_image(temp_path)

            self.assertEqual(preview_path, temp_path / "b-preview.JPG")

    def test_find_preview_image_returns_none_for_missing_or_unsupported_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "notes.md").write_text("ignore", encoding="utf-8")

            self.assertEqual(list_preview_images(temp_path), [])
            self.assertEqual(list_preview_images(temp_path / "missing"), [])
            self.assertIsNone(find_preview_image(temp_path))
            self.assertIsNone(find_preview_image(temp_path / "missing"))


if __name__ == "__main__":
    unittest.main()
