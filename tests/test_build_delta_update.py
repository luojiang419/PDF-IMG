from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.app_info import BUILD_NAME

SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_delta_update import build_patch


class BuildDeltaUpdateTests(unittest.TestCase):
    def test_build_patch_writes_only_changed_and_added_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            from_release = temp_path / "v0.1.19" / BUILD_NAME
            to_release = temp_path / "v0.1.20" / BUILD_NAME
            from_release.mkdir(parents=True)
            to_release.mkdir(parents=True)

            (from_release / "same.txt").write_text("same", encoding="utf-8")
            (from_release / "changed.txt").write_text("before", encoding="utf-8")
            (from_release / "remove.txt").write_text("remove", encoding="utf-8")

            (to_release / "same.txt").write_text("same", encoding="utf-8")
            (to_release / "changed.txt").write_text("after", encoding="utf-8")
            (to_release / "added.txt").write_text("added", encoding="utf-8")

            patch_path = build_patch(
                from_release_dir=from_release.parent,
                to_release_dir=to_release.parent,
            )

            self.assertTrue(patch_path.exists())
            with zipfile.ZipFile(patch_path) as archive:
                manifest = json.loads(archive.read("patch_manifest.json").decode("utf-8"))
                file_paths = sorted(item["path"] for item in manifest["files"])
                self.assertEqual(file_paths, ["added.txt", "changed.txt"])
                self.assertEqual(manifest["removed_files"], ["remove.txt"])
                self.assertIn("payload/added.txt", archive.namelist())
                self.assertIn("payload/changed.txt", archive.namelist())
                self.assertNotIn("payload/same.txt", archive.namelist())


if __name__ == "__main__":
    unittest.main()
