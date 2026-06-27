from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pdf_image_tool.core.app_info import BUILD_NAME


STATE_FILE_NAME = "update_state.json"
UPDATES_DIR_NAME = "updates"
TEST_OVERRIDE_ENV = "PDF_IMG_UPDATE_ROOT"


@dataclass(slots=True)
class PendingUpdate:
    asset_path: str
    asset_kind: str
    target_version: str
    execute_on_next_launch: bool
    fallback_name: str | None = None
    fallback_url: str | None = None
    fallback_sha256: str | None = None
    fallback_size: int | None = None


def app_storage_root() -> Path:
    override_root = os.environ.get(TEST_OVERRIDE_ENV)
    if override_root:
        return Path(override_root).expanduser().resolve()

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / BUILD_NAME
    return Path.home() / "AppData" / "Local" / BUILD_NAME


def updates_cache_dir() -> Path:
    target_dir = app_storage_root() / UPDATES_DIR_NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def update_state_file() -> Path:
    target_path = app_storage_root() / STATE_FILE_NAME
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return target_path


def current_runtime_executable() -> Path:
    return Path(sys.executable).resolve()


def current_runtime_directory() -> Path:
    if getattr(sys, "frozen", False):
        return current_runtime_executable().parent
    return Path(__file__).resolve().parents[3]


def load_update_state() -> dict[str, Any]:
    state_path = update_state_file()
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_update_state(state: dict[str, Any]) -> None:
    update_state_file().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_pending_update() -> PendingUpdate | None:
    state = load_update_state()
    pending = state.get("pending_update")
    if not isinstance(pending, dict):
        return None
    return PendingUpdate(
        asset_path=str(pending["asset_path"]),
        asset_kind=str(pending["asset_kind"]),
        target_version=str(pending["target_version"]),
        execute_on_next_launch=bool(pending.get("execute_on_next_launch", False)),
        fallback_name=pending.get("fallback_name"),
        fallback_url=pending.get("fallback_url"),
        fallback_sha256=pending.get("fallback_sha256"),
        fallback_size=pending.get("fallback_size"),
    )


def save_pending_update(pending_update: PendingUpdate) -> None:
    state = load_update_state()
    state["pending_update"] = asdict(pending_update)
    save_update_state(state)


def clear_pending_update() -> None:
    state = load_update_state()
    state.pop("pending_update", None)
    save_update_state(state)
