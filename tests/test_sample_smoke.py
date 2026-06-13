from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.services.pdf_extractor import extract_images_from_pdf


SAMPLE_ROOT = Path(r"C:\Users\jiang\Desktop\whypark")
SAMPLE_TWO = SAMPLE_ROOT / "2.pdf"


@unittest.skipUnless(SAMPLE_TWO.exists(), "本机 whypark 测试样本不存在")
class WhyparkSmokeTests(unittest.TestCase):
    def test_extracts_images_and_converts_uncommon_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            result = extract_images_from_pdf(SAMPLE_TWO, output_root)

            self.assertIsNone(result.error_message)
            self.assertGreater(result.extracted_count, 0)
            self.assertGreater(result.converted_count, 0)
            self.assertTrue(result.output_dir is not None)
            self.assertFalse(any(path.suffix.lower() == ".jpx" for path in result.output_dir.iterdir()))


if __name__ == "__main__":
    unittest.main()
