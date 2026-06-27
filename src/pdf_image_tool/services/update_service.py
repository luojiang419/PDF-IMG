from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal, Slot

from pdf_image_tool.core.app_info import (
    APP_VERSION,
    BUILD_NAME,
    UPDATE_REPOSITORY,
    manifest_asset_name,
)
from pdf_image_tool.core.update_state import updates_cache_dir
from pdf_image_tool.core.versioning import is_newer_version, normalize_version


ProgressCallback = Callable[[str, int, int | None], None]


class UpdateError(RuntimeError):
    pass


@dataclass(slots=True)
class ReleaseAsset:
    name: str
    url: str
    size: int
    sha256: str


@dataclass(slots=True)
class PatchAsset(ReleaseAsset):
    from_version: str
    to_version: str


@dataclass(slots=True)
class ReleaseManifest:
    version: str
    tag_name: str
    repository: str
    platform: str | None
    full: ReleaseAsset
    patches: list[PatchAsset]


@dataclass(slots=True)
class SelectedUpdate:
    asset_kind: str
    asset: ReleaseAsset
    fallback_asset: ReleaseAsset


@dataclass(slots=True)
class UpdatePreparation:
    status: str
    current_version: str
    target_version: str | None
    asset_kind: str | None
    asset: ReleaseAsset | None
    fallback_asset: ReleaseAsset | None
    local_path: Path | None
    from_cache: bool
    message: str


def normalize_proxy_url(proxy_url: str) -> str:
    cleaned = proxy_url.strip()
    if not cleaned:
        return ""
    if "://" not in cleaned:
        return f"http://{cleaned}"
    return cleaned


def sanitize_proxy_url(proxy_url: str) -> str:
    parsed = urllib.parse.urlsplit(proxy_url)
    hostname = parsed.hostname or ""
    if not hostname:
        return proxy_url
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{hostname}{port}"


def detect_system_proxies(raw_proxies: dict[str, str] | None = None) -> dict[str, str]:
    discovered = urllib.request.getproxies() if raw_proxies is None else raw_proxies
    proxy_map: dict[str, str] = {}
    for scheme in ("https", "http"):
        raw_value = discovered.get(scheme) or discovered.get(scheme.upper())
        if not raw_value:
            continue
        normalized = normalize_proxy_url(str(raw_value))
        if normalized:
            proxy_map[scheme] = normalized
    return proxy_map


def describe_proxy_mode(proxy_map: dict[str, str]) -> str:
    if not proxy_map:
        return "直连网络"
    parts = [f"{scheme}={sanitize_proxy_url(proxy_map[scheme])}" for scheme in ("https", "http") if scheme in proxy_map]
    return f"系统代理（{'，'.join(parts)}）"


def normalize_platform_name(platform_name: str | None) -> str | None:
    if platform_name is None:
        return None
    cleaned = platform_name.strip().lower()
    if not cleaned:
        return None
    aliases = {
        "darwin": "macos",
        "mac": "macos",
        "macos": "macos",
        "osx": "macos",
        "win": "windows",
        "win32": "windows",
        "windows": "windows",
    }
    return aliases.get(cleaned, cleaned)


def runtime_platform_name() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def platform_display_name(platform_name: str | None) -> str:
    normalized = normalize_platform_name(platform_name)
    if normalized == "windows":
        return "Windows"
    if normalized == "macos":
        return "macOS"
    if normalized == "linux":
        return "Linux"
    return normalized or "当前平台"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_release_platform(asset: ReleaseAsset) -> str | None:
    path_text = urllib.parse.urlsplit(asset.url).path.lower()
    name_text = asset.name.lower()
    windows_suffixes = (".exe", ".msi", ".msix", ".msixbundle", ".appx", ".appxbundle")
    mac_suffixes = (".dmg", ".pkg", ".app.zip")
    if path_text.endswith(windows_suffixes) or name_text.endswith(windows_suffixes):
        return "windows"
    if path_text.endswith(mac_suffixes) or name_text.endswith(mac_suffixes):
        return "macos"
    return None


def release_asset_from_manifest(data: dict[str, Any]) -> ReleaseAsset:
    return ReleaseAsset(
        name=str(data["name"]),
        url=str(data["url"]),
        size=int(data["size"]),
        sha256=str(data["sha256"]),
    )


def patch_asset_from_manifest(data: dict[str, Any]) -> PatchAsset:
    return PatchAsset(
        name=str(data["name"]),
        url=str(data["url"]),
        size=int(data["size"]),
        sha256=str(data["sha256"]),
        from_version=normalize_version(str(data["from_version"])),
        to_version=normalize_version(str(data["to_version"])),
    )


class UpdateService:
    def __init__(
        self,
        *,
        repository: str = UPDATE_REPOSITORY,
        timeout_seconds: int = 20,
        urlopen: Callable[..., Any] | None = None,
        proxies: dict[str, str] | None = None,
        platform_name: str | None = None,
    ) -> None:
        self.repository = repository
        self.timeout_seconds = timeout_seconds
        self.proxy_map = detect_system_proxies(proxies)
        self.proxy_mode = describe_proxy_mode(self.proxy_map)
        self.platform_name = normalize_platform_name(platform_name) or runtime_platform_name()
        if urlopen is not None:
            self.urlopen = urlopen
        else:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler(self.proxy_map))
            self.urlopen = opener.open
        self.latest_release_url = f"https://api.github.com/repos/{repository}/releases/latest"

    def build_request(self, url: str, *, accept: str) -> urllib.request.Request:
        return urllib.request.Request(
            url,
            headers={
                "User-Agent": f"{BUILD_NAME}/{APP_VERSION}",
                "Accept": accept,
            },
        )

    def format_http_error_message(self, action: str, code: int) -> str:
        if code == 404:
            return f"{action}：404（GitHub Release 资源不存在或尚未公开）"
        return f"{action}：{code}"

    def read_json(self, url: str) -> dict[str, Any]:
        request = self.build_request(url, accept="application/vnd.github+json")
        try:
            with self.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise UpdateError(self.format_http_error_message("检查更新失败", exc.code)) from exc
        except urllib.error.URLError as exc:
            raise UpdateError(f"检查更新失败：{exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise UpdateError("检查更新失败：返回的 JSON 无法解析。") from exc

    def read_bytes(self, url: str) -> bytes:
        request = self.build_request(url, accept="application/octet-stream")
        try:
            with self.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise UpdateError(self.format_http_error_message("下载更新失败", exc.code)) from exc
        except urllib.error.URLError as exc:
            raise UpdateError(f"下载更新失败：{exc.reason}") from exc

    def fetch_latest_manifest(self) -> ReleaseManifest:
        release_data = self.read_json(self.latest_release_url)
        raw_tag_name = str(release_data.get("tag_name") or "")
        tag_version = normalize_version(raw_tag_name)
        expected_manifest_name = manifest_asset_name(tag_version)

        manifest_url: str | None = None
        for asset in release_data.get("assets", []):
            if str(asset.get("name")) == expected_manifest_name:
                manifest_url = str(asset.get("browser_download_url") or "")
                break

        if not manifest_url:
            raise UpdateError(f"最新发布缺少清单文件：{expected_manifest_name}")

        try:
            manifest_data = json.loads(self.read_bytes(manifest_url).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise UpdateError("更新清单解析失败。") from exc

        manifest_version = normalize_version(str(manifest_data["version"]))
        full_asset = release_asset_from_manifest(dict(manifest_data["full"]))
        manifest_platform = normalize_platform_name(manifest_data.get("platform"))
        if manifest_platform is None:
            manifest_platform = infer_release_platform(full_asset)
        return ReleaseManifest(
            version=manifest_version,
            tag_name=str(manifest_data["tag_name"]),
            repository=str(manifest_data.get("repository") or self.repository),
            platform=manifest_platform,
            full=full_asset,
            patches=[patch_asset_from_manifest(dict(item)) for item in manifest_data.get("patches", [])],
        )

    def is_manifest_compatible(self, manifest: ReleaseManifest) -> bool:
        if manifest.platform is None:
            return True
        return normalize_platform_name(manifest.platform) == self.platform_name

    def select_update(self, manifest: ReleaseManifest, current_version: str) -> SelectedUpdate | None:
        normalized_current = normalize_version(current_version)
        if not is_newer_version(manifest.version, normalized_current):
            return None

        for patch in manifest.patches:
            if patch.from_version == normalized_current and patch.to_version == manifest.version:
                return SelectedUpdate(asset_kind="patch", asset=patch, fallback_asset=manifest.full)

        return SelectedUpdate(asset_kind="full", asset=manifest.full, fallback_asset=manifest.full)

    def verify_cached_asset(self, asset: ReleaseAsset, path: Path) -> bool:
        return path.exists() and hash_file(path) == asset.sha256

    def download_asset(
        self,
        asset: ReleaseAsset,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[Path, bool]:
        cache_path = updates_cache_dir() / asset.name
        if self.verify_cached_asset(asset, cache_path):
            if progress_callback is not None:
                progress_callback(f"已复用缓存更新包：{asset.name}", asset.size, asset.size)
            return cache_path, True

        temp_path = cache_path.with_name(f"{cache_path.name}.download")
        if temp_path.exists():
            temp_path.unlink()

        request = self.build_request(asset.url, accept="application/octet-stream")
        try:
            with self.urlopen(request, timeout=self.timeout_seconds) as response, temp_path.open("wb") as handle:
                total_text = response.headers.get("Content-Length")
                total = int(total_text) if total_text and total_text.isdigit() else None
                downloaded = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback is not None:
                        progress_callback(f"正在下载更新包：{asset.name}", downloaded, total)
        except urllib.error.HTTPError as exc:
            raise UpdateError(f"下载更新包失败：{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise UpdateError(f"下载更新包失败：{exc.reason}") from exc

        temp_hash = hash_file(temp_path)
        if temp_hash != asset.sha256:
            temp_path.unlink(missing_ok=True)
            raise UpdateError("下载完成但文件校验失败。")

        temp_path.replace(cache_path)
        return cache_path, False

    def prepare_update(
        self,
        *,
        current_version: str = APP_VERSION,
        progress_callback: ProgressCallback | None = None,
    ) -> UpdatePreparation:
        manifest = self.fetch_latest_manifest()
        if not self.is_manifest_compatible(manifest):
            current_platform = platform_display_name(self.platform_name)
            manifest_platform = platform_display_name(manifest.platform)
            return UpdatePreparation(
                status="up_to_date",
                current_version=normalize_version(current_version),
                target_version=manifest.version,
                asset_kind=None,
                asset=None,
                fallback_asset=None,
                local_path=None,
                from_cache=False,
                message=f"最新发布仅包含 {manifest_platform} 更新包，当前 {current_platform} 已跳过。",
            )
        selection = self.select_update(manifest, current_version)
        if selection is None:
            return UpdatePreparation(
                status="up_to_date",
                current_version=normalize_version(current_version),
                target_version=manifest.version,
                asset_kind=None,
                asset=None,
                fallback_asset=None,
                local_path=None,
                from_cache=False,
                message="当前已是最新版本。",
            )

        local_path, from_cache = self.download_asset(selection.asset, progress_callback=progress_callback)
        action_label = "增量补丁" if selection.asset_kind == "patch" else "全量安装包"
        source_label = "已复用缓存" if from_cache else "已完成下载"
        return UpdatePreparation(
            status="update_ready",
            current_version=normalize_version(current_version),
            target_version=manifest.version,
            asset_kind=selection.asset_kind,
            asset=selection.asset,
            fallback_asset=selection.fallback_asset,
            local_path=local_path,
            from_cache=from_cache,
            message=f"发现新版本 v{manifest.version}，{source_label}{action_label}。",
        )


class UpdateCheckWorker(QObject):
    status_message = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, service: UpdateService, *, current_version: str) -> None:
        super().__init__()
        self.service = service
        self.current_version = current_version

    def emit_progress(self, message: str, downloaded: int, total: int | None) -> None:
        if total and total > 0:
            percent = int(downloaded / total * 100)
            self.status_message.emit(f"{message}（{percent}%）")
            return
        self.status_message.emit(message)

    @Slot()
    def run(self) -> None:
        try:
            self.status_message.emit(f"正在检查 GitHub 最新发布版本（{self.service.proxy_mode}）。")
            result = self.service.prepare_update(
                current_version=self.current_version,
                progress_callback=self.emit_progress,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
