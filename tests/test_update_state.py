from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.update_state import (
    PendingUpdate,
    TEST_OVERRIDE_ENV,
    app_storage_root,
    clear_pending_update,
    load_pending_update,
    save_pending_update,
    updates_cache_dir,
)


class UpdateStateTests(unittest.TestCase):
    def test_save_and_clear_pending_update(self) -> None:
        previous_override = os.environ.get(TEST_OVERRIDE_ENV)
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ[TEST_OVERRIDE_ENV] = temp_dir
            pending_update = PendingUpdate(
                asset_path="C:/updates/patch.zip",
                asset_kind="patch",
                target_version="0.1.20",
                execute_on_next_launch=True,
                fallback_name="setup.exe",
                fallback_url="https://example.com/setup.exe",
                fallback_sha256="abc123",
                fallback_size=2048,
            )

            save_pending_update(pending_update)
            loaded = load_pending_update()
            self.assertEqual(loaded, pending_update)
            self.assertEqual(app_storage_root(), Path(temp_dir))
            self.assertTrue(updates_cache_dir().exists())

            clear_pending_update()
            self.assertIsNone(load_pending_update())

        if previous_override is None:
            os.environ.pop(TEST_OVERRIDE_ENV, None)
        else:
            os.environ[TEST_OVERRIDE_ENV] = previous_override


if __name__ == "__main__":
    unittest.main()
