from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf

from pdf_image_tool.services.pdf_extractor import extract_images_from_pdf


def build_png_bytes() -> bytes:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 2, 2), False)
    return pixmap.tobytes("png")


def build_jpeg_bytes() -> bytes:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 2, 2), False)
    return pixmap.tobytes("jpeg")


class PdfExtractorTests(unittest.TestCase):
    def create_pdf_with_images(self, pdf_path: Path) -> None:
        document = pymupdf.open()
        page = document.new_page(width=300, height=200)
        page.insert_image(pymupdf.Rect(24, 24, 124, 124), stream=build_png_bytes())
        page.insert_image(pymupdf.Rect(150, 24, 260, 124), stream=build_jpeg_bytes())
        document.save(pdf_path.as_posix())
        document.close()

    def create_blank_pdf(self, pdf_path: Path) -> None:
        document = pymupdf.open()
        document.new_page(width=200, height=200)
        document.save(pdf_path.as_posix())
        document.close()

    def create_encrypted_pdf(self, pdf_path: Path) -> None:
        document = pymupdf.open()
        page = document.new_page(width=200, height=200)
        page.insert_image(pymupdf.Rect(30, 30, 130, 130), stream=build_png_bytes())
        document.save(
            pdf_path.as_posix(),
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner",
            user_pw="user",
        )
        document.close()

    def test_extracts_native_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_path = temp_path / "sample.pdf"
            output_root = temp_path / "output"
            self.create_pdf_with_images(pdf_path)

            result = extract_images_from_pdf(pdf_path, output_root)

            self.assertIsNone(result.error_message)
            self.assertEqual(result.status, "success")
            self.assertEqual(result.extracted_count, 2)
            self.assertEqual(result.converted_count, 0)
            self.assertTrue(result.output_dir and result.output_dir.exists())

            exported_files = sorted(path.name for path in result.output_dir.iterdir())
            self.assertEqual(exported_files, ["page-001_img-001.png", "page-001_img-002.jpeg"])

    def test_handles_blank_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_path = temp_path / "blank.pdf"
            output_root = temp_path / "output"
            self.create_blank_pdf(pdf_path)

            result = extract_images_from_pdf(pdf_path, output_root)

            self.assertEqual(result.status, "no_images")
            self.assertEqual(result.extracted_count, 0)
            self.assertIsNone(result.error_message)

    def test_uses_incremented_output_folder_when_name_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_path = temp_path / "duplicate.pdf"
            output_root = temp_path / "output"
            output_root.mkdir()
            (output_root / "duplicate").mkdir()
            self.create_pdf_with_images(pdf_path)

            result = extract_images_from_pdf(pdf_path, output_root)

            self.assertTrue(result.output_dir is not None)
            self.assertEqual(result.output_dir.name, "duplicate_02")

    def test_reports_encrypted_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_path = temp_path / "secret.pdf"
            output_root = temp_path / "output"
            self.create_encrypted_pdf(pdf_path)

            result = extract_images_from_pdf(pdf_path, output_root)

            self.assertEqual(result.status, "failed")
            self.assertIsNotNone(result.error_message)
            self.assertIn("加密", result.error_message)


if __name__ == "__main__":
    unittest.main()
