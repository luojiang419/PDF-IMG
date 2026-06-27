from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.app_info import manifest_asset_name
from pdf_image_tool.core.update_state import TEST_OVERRIDE_ENV
from pdf_image_tool.services.update_service import (
    UpdateService,
    detect_system_proxies,
    describe_proxy_mode,
    resolve_github_token,
)


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
    def test_resolve_github_token_prefers_environment_token(self) -> None:
        previous_env = {name: os.environ.get(name) for name in ("PDF_IMG_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")}
        try:
            os.environ["PDF_IMG_GITHUB_TOKEN"] = "env-token"
            self.assertEqual(resolve_github_token(), "env-token")
        finally:
            for name, value in previous_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    @patch("pdf_image_tool.services.update_service.find_gh_command", return_value="/opt/homebrew/bin/gh")
    @patch("pdf_image_tool.services.update_service.subprocess.run")
    def test_resolve_github_token_reads_gh_cli_token(self, mock_run, mock_find_gh_command) -> None:
        previous_env = {name: os.environ.get(name) for name in ("PDF_IMG_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")}
        try:
            for name in previous_env:
                os.environ.pop(name, None)
            mock_run.return_value = subprocess.CompletedProcess(
                args=["gh", "auth", "token"],
                returncode=0,
                stdout="gh-token\n",
                stderr="",
            )
            self.assertEqual(resolve_github_token(), "gh-token")
        finally:
            for name, value in previous_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

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

    def test_prepare_update_prefers_patch_and_reuses_cached_asset(self) -> None:
        previous_override = os.environ.get(TEST_OVERRIDE_ENV)
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ[TEST_OVERRIDE_ENV] = temp_dir
            patch_bytes = b"patch-binary"
            full_bytes = b"full-installer"
            patch_sha = hashlib.sha256(patch_bytes).hexdigest()
            full_sha = hashlib.sha256(full_bytes).hexdigest()

            manifest = {
                "version": "0.1.20",
                "tag_name": "v0.1.20",
                "repository": "demo/repo",
                "full": {
                    "name": "setup.exe",
                    "url": "https://example.com/setup.exe",
                    "size": len(full_bytes),
                    "sha256": full_sha,
                },
                "patches": [
                    {
                        "from_version": "0.1.19",
                        "to_version": "0.1.20",
                        "name": "patch.zip",
                        "url": "https://example.com/patch.zip",
                        "size": len(patch_bytes),
                        "sha256": patch_sha,
                    }
                ],
            }
            release_json = {
                "tag_name": "v0.1.20",
                "assets": [
                    {
                        "name": manifest_asset_name("0.1.20"),
                        "url": "https://api.github.com/repos/demo/repo/releases/assets/manifest",
                        "browser_download_url": "https://example.com/manifest.json",
                    },
                    {
                        "name": "patch.zip",
                        "url": "https://api.github.com/repos/demo/repo/releases/assets/patch",
                        "browser_download_url": "https://example.com/patch.zip",
                    },
                    {
                        "name": "setup.exe",
                        "url": "https://api.github.com/repos/demo/repo/releases/assets/setup",
                        "browser_download_url": "https://example.com/setup.exe",
                    }
                ],
            }

            def fake_urlopen(request, timeout=0):
                url = request.full_url
                if url.endswith("/releases/latest"):
                    return FakeResponse(json.dumps(release_json).encode("utf-8"))
                if url.endswith("/assets/manifest"):
                    return FakeResponse(json.dumps(manifest).encode("utf-8"))
                if url.endswith("/assets/patch"):
                    return FakeResponse(patch_bytes, headers={"Content-Length": str(len(patch_bytes))})
                if url.endswith("/assets/setup"):
                    return FakeResponse(full_bytes, headers={"Content-Length": str(len(full_bytes))})
                raise AssertionError(f"unexpected url: {url}")

            service = UpdateService(
                repository="demo/repo",
                urlopen=fake_urlopen,
                proxies={"https": "127.0.0.1:7890"},
                github_token="",
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

        if previous_override is None:
            os.environ.pop(TEST_OVERRIDE_ENV, None)
        else:
            os.environ[TEST_OVERRIDE_ENV] = previous_override

    def test_prepare_update_sends_bearer_token_when_configured(self) -> None:
        previous_override = os.environ.get(TEST_OVERRIDE_ENV)
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ[TEST_OVERRIDE_ENV] = temp_dir
            patch_bytes = b"patch-binary"
            full_bytes = b"full-installer"
            patch_sha = hashlib.sha256(patch_bytes).hexdigest()
            full_sha = hashlib.sha256(full_bytes).hexdigest()

            manifest = {
                "version": "0.1.21",
                "tag_name": "v0.1.21",
                "repository": "demo/repo",
                "full": {
                    "name": "setup.exe",
                    "url": "https://example.com/setup.exe",
                    "size": len(full_bytes),
                    "sha256": full_sha,
                },
                "patches": [
                    {
                        "from_version": "0.1.20",
                        "to_version": "0.1.21",
                        "name": "patch.zip",
                        "url": "https://example.com/patch.zip",
                        "size": len(patch_bytes),
                        "sha256": patch_sha,
                    }
                ],
            }
            release_json = {
                "tag_name": "v0.1.21",
                "assets": [
                    {
                        "name": manifest_asset_name("0.1.21"),
                        "url": "https://api.github.com/repos/demo/repo/releases/assets/manifest",
                        "browser_download_url": "https://example.com/manifest.json",
                    },
                    {
                        "name": "patch.zip",
                        "url": "https://api.github.com/repos/demo/repo/releases/assets/patch",
                        "browser_download_url": "https://example.com/patch.zip",
                    },
                    {
                        "name": "setup.exe",
                        "url": "https://api.github.com/repos/demo/repo/releases/assets/setup",
                        "browser_download_url": "https://example.com/setup.exe",
                    }
                ],
            }
            auth_headers: list[str | None] = []

            def fake_urlopen(request, timeout=0):
                headers = {key.title(): value for key, value in request.header_items()}
                auth_headers.append(headers.get("Authorization"))
                url = request.full_url
                if url.endswith("/releases/latest"):
                    return FakeResponse(json.dumps(release_json).encode("utf-8"))
                if url.endswith("/assets/manifest"):
                    return FakeResponse(json.dumps(manifest).encode("utf-8"))
                if url.endswith("/assets/patch"):
                    return FakeResponse(patch_bytes, headers={"Content-Length": str(len(patch_bytes))})
                if url.endswith("/assets/setup"):
                    return FakeResponse(full_bytes, headers={"Content-Length": str(len(full_bytes))})
                raise AssertionError(f"unexpected url: {url}")

            service = UpdateService(
                repository="demo/repo",
                urlopen=fake_urlopen,
                proxies={},
                github_token="demo-token",
            )
            result = service.prepare_update(current_version="0.1.20")
            self.assertEqual(result.status, "update_ready")
            self.assertTrue(auth_headers)
            self.assertTrue(all(header == "Bearer demo-token" for header in auth_headers))

        if previous_override is None:
            os.environ.pop(TEST_OVERRIDE_ENV, None)
        else:
            os.environ[TEST_OVERRIDE_ENV] = previous_override


if __name__ == "__main__":
    unittest.main()
