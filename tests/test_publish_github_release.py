from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pdf_image_tool.core.app_info import legacy_manifest_asset_name, manifest_asset_name
from publish_github_release import write_release_manifests


class PublishGithubReleaseTests(unittest.TestCase):
    def test_write_release_manifests_writes_windows_platform_and_legacy_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir)
            installer_path = release_dir / "setup.exe"
            patch_path = release_dir / "patch.zip"
            installer_path.write_bytes(b"setup")
            patch_path.write_bytes(b"patch")

            manifest_paths = write_release_manifests(
                release_dir=release_dir,
                version="0.1.22",
                repository="demo/repo",
                installer_path=installer_path,
                patch_path=patch_path,
                previous_version="0.1.21",
                platform_name="windows",
            )

            self.assertEqual(
                sorted(path.name for path in manifest_paths),
                sorted(
                    [
                        manifest_asset_name("0.1.22", "windows"),
                        legacy_manifest_asset_name("0.1.22"),
                    ]
                ),
            )
            manifest_payloads = [json.loads(path.read_text(encoding="utf-8")) for path in manifest_paths]
            self.assertEqual(manifest_payloads[0], manifest_payloads[1])
            self.assertEqual(manifest_payloads[0]["platform"], "windows")
            self.assertEqual(manifest_payloads[0]["patches"][0]["from_version"], "0.1.21")

    def test_write_release_manifests_writes_only_platform_manifest_for_macos(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir)
            installer_path = release_dir / "app.dmg"
            installer_path.write_bytes(b"dmg")

            manifest_paths = write_release_manifests(
                release_dir=release_dir,
                version="0.1.22",
                repository="demo/repo",
                installer_path=installer_path,
                patch_path=None,
                previous_version=None,
                platform_name="macos",
            )

            self.assertEqual(
                [path.name for path in manifest_paths],
                [manifest_asset_name("0.1.22", "macos")],
            )
            manifest_payload = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["platform"], "macos")
            self.assertEqual(manifest_payload["patches"], [])


if __name__ == "__main__":
    unittest.main()
