from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.versioning import bump_patch_version, compare_versions, is_newer_version, normalize_version


class VersioningTests(unittest.TestCase):
    def test_normalize_version_handles_prefixed_and_plain_values(self) -> None:
        self.assertEqual(normalize_version("v0.1.19"), "0.1.19")
        self.assertEqual(normalize_version("0.1.20"), "0.1.20")

    def test_compare_versions_orders_versions_correctly(self) -> None:
        self.assertEqual(compare_versions("0.1.19", "0.1.19"), 0)
        self.assertEqual(compare_versions("0.1.20", "0.1.19"), 1)
        self.assertEqual(compare_versions("0.1.18", "0.1.19"), -1)
        self.assertTrue(is_newer_version("0.1.20", "0.1.19"))
        self.assertFalse(is_newer_version("0.1.19", "0.1.19"))

    def test_bump_patch_version_returns_plain_semver(self) -> None:
        self.assertEqual(bump_patch_version("0.1.19"), "0.1.20")
        self.assertEqual(bump_patch_version("v0.1.20"), "0.1.21")


if __name__ == "__main__":
    unittest.main()
