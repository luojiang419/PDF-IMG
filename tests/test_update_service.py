from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.app_info import legacy_manifest_asset_name, manifest_asset_name, patch_asset_name
from pdf_image_tool.core.update_state import TEST_OVERRIDE_ENV
from pdf_image_tool.services.update_service import UpdateService, detect_system_proxies, describe_proxy_mode


class FakeResponse:
    def __init__(self, body: bytes, *, headers: dict[str, str] | None = None) -> None:
        self._stream = io.BytesIO(body)
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


class UpdateServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_override = os.environ.get(TEST_OVERRIDE_ENV)
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ[TEST_OVERRIDE_ENV] = self.temp_dir.name

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        if self.previous_override is None:
            os.environ.pop(TEST_OVERRIDE_ENV, None)
        else:
            os.environ[TEST_OVERRIDE_ENV] = self.previous_override

    def test_detect_system_proxies_normalizes_host_port_values(self) -> None:
        proxies = detect_system_proxies({"https": "127.0.0.1:7890", "http": "http://127.0.0.1:7891"})
        self.assertEqual(
            proxies,
            {
                "https": "http://127.0.0.1:7890",
                "http": "http://127.0.0.1:7891",
            },
        )
        self.assertEqual(
            describe_proxy_mode(proxies),
            "系统代理（https=http://127.0.0.1:7890，http=http://127.0.0.1:7891）",
        )

    def test_prepare_update_prefers_patch_and_reuses_cached_asset_on_windows(self) -> None:
        patch_bytes = b"patch-binary"
        full_bytes = b"full-installer"
        patch_name = patch_asset_name("0.1.19", "0.1.20", "windows")
        full_name = "PDF-IMG-Extractor-v0.1.20-Setup.exe"
        manifest = {
            "version": "0.1.20",
            "tag_name": "v0.1.20",
            "repository": "demo/repo",
            "platform": "windows",
            "full": {
                "name": full_name,
                "url": f"https://example.com/{full_name}",
                "size": len(full_bytes),
                "sha256": hashlib.sha256(full_bytes).hexdigest(),
            },
            "patches": [
                {
                    "from_version": "0.1.19",
                    "to_version": "0.1.20",
                    "name": patch_name,
                    "url": f"https://example.com/{patch_name}",
                    "size": len(patch_bytes),
                    "sha256": hashlib.sha256(patch_bytes).hexdigest(),
                }
            ],
        }
        release_json = {
            "tag_name": "v0.1.20",
            "assets": [
                {
                    "name": manifest_asset_name("0.1.20", "windows"),
                    "browser_download_url": "https://example.com/windows-manifest.json",
                }
            ],
        }
        requested_urls: list[str] = []

        def fake_urlopen(request, timeout=0):
            requested_urls.append(request.full_url)
            url = request.full_url
            if "/releases?per_page=" in url:
                return FakeResponse(json.dumps([release_json]).encode("utf-8"))
            if url.endswith("/windows-manifest.json"):
                return FakeResponse(json.dumps(manifest).encode("utf-8"))
            if url.endswith(f"/{patch_name}"):
                return FakeResponse(patch_bytes, headers={"Content-Length": str(len(patch_bytes))})
            if url.endswith(f"/{full_name}"):
                return FakeResponse(full_bytes, headers={"Content-Length": str(len(full_bytes))})
            raise AssertionError(f"unexpected url: {url}")

        service = UpdateService(
            repository="demo/repo",
            urlopen=fake_urlopen,
            proxies={"https": "127.0.0.1:7890"},
            platform_name="windows",
        )
        self.assertEqual(service.proxy_mode, "系统代理（https=http://127.0.0.1:7890）")

        first = service.prepare_update(current_version="0.1.19")
        self.assertEqual(first.status, "update_ready")
        self.assertEqual(first.asset_kind, "patch")
        self.assertFalse(first.from_cache)
        self.assertTrue(first.local_path is not None and first.local_path.exists())

        second = service.prepare_update(current_version="0.1.19")
        self.assertEqual(second.asset_kind, "patch")
        self.assertTrue(second.from_cache)

        fallback = service.prepare_update(current_version="0.1.18")
        self.assertEqual(fallback.asset_kind, "full")
        self.assertEqual(fallback.target_version, "0.1.20")

        latest = service.prepare_update(current_version="0.1.20")
        self.assertEqual(latest.status, "up_to_date")
        self.assertIsNone(latest.asset)
        self.assertTrue(any(url.endswith(f"/{patch_name}") for url in requested_urls))
        self.assertTrue(any(url.endswith(f"/{full_name}") for url in requested_urls))

    def test_prepare_update_skips_newer_other_platform_release(self) -> None:
        full_bytes = b"full-installer"
        windows_manifest = {
            "version": "0.1.20",
            "tag_name": "v0.1.20",
            "repository": "demo/repo",
            "platform": "windows",
            "full": {
                "name": "setup.exe",
                "url": "https://example.com/setup.exe",
                "size": len(full_bytes),
                "sha256": hashlib.sha256(full_bytes).hexdigest(),
            },
            "patches": [],
        }
        mac_manifest = {
            "version": "0.1.21",
            "tag_name": "v0.1.21",
            "repository": "demo/repo",
            "platform": "macos",
            "full": {
                "name": "app.dmg",
                "url": "https://example.com/app.dmg",
                "size": 10,
                "sha256": "0" * 64,
            },
            "patches": [],
        }
        release_list = [
            {
                "tag_name": "v0.1.21",
                "assets": [
                    {
                        "name": manifest_asset_name("0.1.21", "macos"),
                        "browser_download_url": "https://example.com/macos-manifest.json",
                    }
                ],
            },
            {
                "tag_name": "v0.1.20",
                "assets": [
                    {
                        "name": manifest_asset_name("0.1.20", "windows"),
                        "browser_download_url": "https://example.com/windows-manifest.json",
                    }
                ],
            },
        ]

        def fake_urlopen(request, timeout=0):
            url = request.full_url
            if "/releases?per_page=" in url:
                return FakeResponse(json.dumps(release_list).encode("utf-8"))
            if url.endswith("/macos-manifest.json"):
                return FakeResponse(json.dumps(mac_manifest).encode("utf-8"))
            if url.endswith("/windows-manifest.json"):
                return FakeResponse(json.dumps(windows_manifest).encode("utf-8"))
            if url.endswith("/setup.exe"):
                return FakeResponse(full_bytes, headers={"Content-Length": str(len(full_bytes))})
            raise AssertionError(f"unexpected url: {url}")

        service = UpdateService(repository="demo/repo", urlopen=fake_urlopen, platform_name="windows")
        result = service.prepare_update(current_version="0.1.19")
        self.assertEqual(result.status, "update_ready")
        self.assertEqual(result.target_version, "0.1.20")
        self.assertEqual(result.asset_kind, "full")

    def test_prepare_update_supports_legacy_windows_manifest_name(self) -> None:
        full_bytes = b"legacy-full-installer"
        manifest = {
            "version": "0.1.20",
            "tag_name": "v0.1.20",
            "repository": "demo/repo",
            "full": {
                "name": "setup.exe",
                "url": "https://example.com/setup.exe",
                "size": len(full_bytes),
                "sha256": hashlib.sha256(full_bytes).hexdigest(),
            },
            "patches": [],
        }
        release_list = [
            {
                "tag_name": "v0.1.20",
                "assets": [
                    {
                        "name": legacy_manifest_asset_name("0.1.20"),
                        "browser_download_url": "https://example.com/legacy-manifest.json",
                    }
                ],
            }
        ]

        def fake_urlopen(request, timeout=0):
            url = request.full_url
            if "/releases?per_page=" in url:
                return FakeResponse(json.dumps(release_list).encode("utf-8"))
            if url.endswith("/legacy-manifest.json"):
                return FakeResponse(json.dumps(manifest).encode("utf-8"))
            if url.endswith("/setup.exe"):
                return FakeResponse(full_bytes, headers={"Content-Length": str(len(full_bytes))})
            raise AssertionError(f"unexpected url: {url}")

        service = UpdateService(repository="demo/repo", urlopen=fake_urlopen, platform_name="windows")
        result = service.prepare_update(current_version="0.1.19")
        self.assertEqual(result.status, "update_ready")
        self.assertEqual(result.target_version, "0.1.20")
        self.assertEqual(result.asset_kind, "full")

    def test_prepare_update_prefers_platform_manifest_over_legacy_name(self) -> None:
        full_bytes = b"windows-full-installer"
        windows_manifest = {
            "version": "0.1.23",
            "tag_name": "v0.1.23",
            "repository": "demo/repo",
            "platform": "windows",
            "full": {
                "name": "setup.exe",
                "url": "https://example.com/setup.exe",
                "size": len(full_bytes),
                "sha256": hashlib.sha256(full_bytes).hexdigest(),
            },
            "patches": [],
        }
        legacy_mac_manifest = {
            "version": "0.1.23",
            "tag_name": "v0.1.23",
            "repository": "demo/repo",
            "platform": "macos",
            "full": {
                "name": "app.dmg",
                "url": "https://example.com/app.dmg",
                "size": 10,
                "sha256": "0" * 64,
            },
            "patches": [],
        }
        release_list = [
            {
                "tag_name": "v0.1.23",
                "assets": [
                    {
                        "name": legacy_manifest_asset_name("0.1.23"),
                        "browser_download_url": "https://example.com/legacy-manifest.json",
                    },
                    {
                        "name": manifest_asset_name("0.1.23", "windows"),
                        "browser_download_url": "https://example.com/windows-manifest.json",
                    },
                ],
            }
        ]
        requested_urls: list[str] = []

        def fake_urlopen(request, timeout=0):
            requested_urls.append(request.full_url)
            url = request.full_url
            if "/releases?per_page=" in url:
                return FakeResponse(json.dumps(release_list).encode("utf-8"))
            if url.endswith("/windows-manifest.json"):
                return FakeResponse(json.dumps(windows_manifest).encode("utf-8"))
            if url.endswith("/legacy-manifest.json"):
                return FakeResponse(json.dumps(legacy_mac_manifest).encode("utf-8"))
            if url.endswith("/setup.exe"):
                return FakeResponse(full_bytes, headers={"Content-Length": str(len(full_bytes))})
            if url.endswith("/app.dmg"):
                raise AssertionError("Windows 不应下载 macOS DMG")
            raise AssertionError(f"unexpected url: {url}")

        service = UpdateService(repository="demo/repo", urlopen=fake_urlopen, platform_name="windows")
        result = service.prepare_update(current_version="0.1.22")
        self.assertEqual(result.status, "update_ready")
        self.assertEqual(result.target_version, "0.1.23")
        self.assertEqual(result.asset_kind, "full")
        self.assertTrue(any(url.endswith("/windows-manifest.json") for url in requested_urls))
        self.assertFalse(any(url.endswith("/legacy-manifest.json") for url in requested_urls))

    def test_prepare_update_ignores_legacy_windows_manifest_on_macos(self) -> None:
        manifest = {
            "version": "0.1.20",
            "tag_name": "v0.1.20",
            "repository": "demo/repo",
            "full": {
                "name": "setup.exe",
                "url": "https://example.com/setup.exe",
                "size": 10,
                "sha256": "0" * 64,
            },
            "patches": [],
        }
        release_list = [
            {
                "tag_name": "v0.1.20",
                "assets": [
                    {
                        "name": legacy_manifest_asset_name("0.1.20"),
                        "browser_download_url": "https://example.com/legacy-manifest.json",
                    }
                ],
            }
        ]

        def fake_urlopen(request, timeout=0):
            url = request.full_url
            if "/releases?per_page=" in url:
                return FakeResponse(json.dumps(release_list).encode("utf-8"))
            if url.endswith("/legacy-manifest.json"):
                return FakeResponse(json.dumps(manifest).encode("utf-8"))
            if url.endswith("/setup.exe"):
                raise AssertionError("macOS 不应下载旧 Windows 安装包")
            raise AssertionError(f"unexpected url: {url}")

        service = UpdateService(repository="demo/repo", urlopen=fake_urlopen, platform_name="macos")
        result = service.prepare_update(current_version="0.1.19")
        self.assertEqual(result.status, "up_to_date")
        self.assertIsNone(result.target_version)
        self.assertIn("macOS", result.message)

    def test_prepare_update_downloads_macos_dmg_release(self) -> None:
        dmg_bytes = b"macos-dmg"
        dmg_name = "PDF-IMG-Extractor-v0.1.23-mac-x86_64.dmg"
        manifest = {
            "version": "0.1.23",
            "tag_name": "v0.1.23",
            "repository": "demo/repo",
            "platform": "macos",
            "full": {
                "name": dmg_name,
                "url": f"https://example.com/{dmg_name}",
                "size": len(dmg_bytes),
                "sha256": hashlib.sha256(dmg_bytes).hexdigest(),
            },
            "patches": [],
        }
        release_list = [
            {
                "tag_name": "v0.1.23",
                "assets": [
                    {
                        "name": manifest_asset_name("0.1.23", "macos"),
                        "browser_download_url": "https://example.com/macos-manifest.json",
                    }
                ],
            }
        ]

        def fake_urlopen(request, timeout=0):
            url = request.full_url
            if "/releases?per_page=" in url:
                return FakeResponse(json.dumps(release_list).encode("utf-8"))
            if url.endswith("/macos-manifest.json"):
                return FakeResponse(json.dumps(manifest).encode("utf-8"))
            if url.endswith(f"/{dmg_name}"):
                return FakeResponse(dmg_bytes, headers={"Content-Length": str(len(dmg_bytes))})
            raise AssertionError(f"unexpected url: {url}")

        service = UpdateService(repository="demo/repo", urlopen=fake_urlopen, platform_name="macos")
        result = service.prepare_update(current_version="0.1.22")
        self.assertEqual(result.status, "update_ready")
        self.assertEqual(result.target_version, "0.1.23")
        self.assertEqual(result.asset_kind, "full")
        self.assertTrue(result.local_path is not None and result.local_path.exists())


if __name__ == "__main__":
    unittest.main()
