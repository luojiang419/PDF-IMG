from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from pdf_image_tool.core.app_info import APP_ICON_PARTS, APP_NAME, APP_VERSION
from pdf_image_tool.core.paths import resource_path
from pdf_image_tool.core.update_state import (
    PendingUpdate,
    clear_pending_update,
    current_runtime_directory,
    current_runtime_executable,
    load_pending_update,
    save_pending_update,
    updates_cache_dir,
)
from pdf_image_tool.core.versioning import is_newer_version
from pdf_image_tool.services.update_service import UpdateCheckWorker, UpdatePreparation, UpdateService
from pdf_image_tool.ui.main_window import MainWindow


DEFAULT_THEME_NAME = "dark"
THEME_STYLESHEET_PATHS = {
    "dark": ("assets", "theme.qss"),
    "light": ("assets", "theme_light.qss"),
}


def normalize_theme_name(theme_name: str) -> str:
    return theme_name if theme_name in THEME_STYLESHEET_PATHS else DEFAULT_THEME_NAME


def load_stylesheet(theme_name: str = DEFAULT_THEME_NAME) -> str:
    stylesheet_path = resource_path(*THEME_STYLESHEET_PATHS[normalize_theme_name(theme_name)])
    if not stylesheet_path.exists():
        return ""
    return stylesheet_path.read_text(encoding="utf-8")


def load_app_icon() -> QIcon:
    icon_path = resource_path(*APP_ICON_PARTS)
    if not icon_path.exists():
        return QIcon()
    return QIcon(str(icon_path))


def launch_update_process(
    pending_update: PendingUpdate,
    *,
    parent: MainWindow | None = None,
) -> bool:
    if not getattr(sys, "frozen", False):
        if parent is not None:
            QMessageBox.information(
                parent,
                "开发环境",
                "当前是源码运行环境，已完成更新包下载，但自动安装只在打包后的安装版中可用。",
            )
        return False

    update_script = resource_path("scripts", "apply_update.ps1")
    if not update_script.exists():
        raise RuntimeError(f"未找到更新接管脚本：{update_script}")

    asset_path = Path(pending_update.asset_path)
    if not asset_path.exists():
        raise RuntimeError(f"未找到更新包：{asset_path}")

    command = [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(update_script),
        "-WaitPid",
        str(os.getpid()),
        "-AppExePath",
        str(current_runtime_executable()),
        "-AppDir",
        str(current_runtime_directory()),
        "-AssetPath",
        str(asset_path),
        "-AssetKind",
        pending_update.asset_kind,
        "-CurrentVersion",
        APP_VERSION,
        "-TargetVersion",
        pending_update.target_version,
    ]

    if pending_update.fallback_name and pending_update.fallback_url and pending_update.fallback_sha256:
        fallback_path = updates_cache_dir() / pending_update.fallback_name
        command.extend(
            [
                "-FallbackName",
                pending_update.fallback_name,
                "-FallbackUrl",
                pending_update.fallback_url,
                "-FallbackSha256",
                pending_update.fallback_sha256,
                "-FallbackPath",
                str(fallback_path),
            ]
        )

    subprocess.Popen(command, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True


def launch_pending_update_if_needed() -> bool:
    pending_update = load_pending_update()
    if pending_update is None or not pending_update.execute_on_next_launch:
        return False

    if not is_newer_version(pending_update.target_version, APP_VERSION):
        clear_pending_update()
        return False

    if not getattr(sys, "frozen", False):
        clear_pending_update()
        return False

    clear_pending_update()
    try:
        return launch_update_process(pending_update)
    except Exception:
        return False


class UpdateCoordinator(QObject):
    def __init__(self, app: QApplication, window: MainWindow) -> None:
        super().__init__(window)
        self.app = app
        self.window = window
        self.service = UpdateService()
        self.update_thread: QThread | None = None
        self.update_worker: UpdateCheckWorker | None = None
        self.active_request_is_manual = False
        self.window.manual_update_check_requested.connect(self.start_manual_check)

    def startup_check(self) -> None:
        self.start_check(manual=False)

    def start_manual_check(self) -> None:
        self.start_check(manual=True)

    def start_check(self, *, manual: bool) -> None:
        if self.update_thread is not None:
            if manual:
                QMessageBox.information(self.window, "检查更新", "当前正在检查更新，请稍候。")
            return

        self.active_request_is_manual = manual
        self.window.set_update_busy(True)
        self.window.set_update_status(f"正在检查 GitHub 最新发布版本（{self.service.proxy_mode}）。")
        self.window.append_log(
            f"{'开始手动检查软件更新' if manual else '软件启动后开始自动检查更新'}，当前网络方式：{self.service.proxy_mode}。"
        )

        self.update_thread = QThread(self)
        self.update_worker = UpdateCheckWorker(self.service, current_version=APP_VERSION)
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.status_message.connect(self.on_status_message)
        self.update_worker.finished.connect(self.on_update_finished)
        self.update_worker.failed.connect(self.on_update_failed)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.failed.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_worker.failed.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.on_update_thread_finished)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.start()

    def build_pending_update(
        self,
        result: UpdatePreparation,
        *,
        execute_on_next_launch: bool,
    ) -> PendingUpdate:
        fallback = result.fallback_asset
        return PendingUpdate(
            asset_path=str(result.local_path),
            asset_kind=str(result.asset_kind),
            target_version=str(result.target_version),
            execute_on_next_launch=execute_on_next_launch,
            fallback_name=fallback.name if fallback is not None else None,
            fallback_url=fallback.url if fallback is not None else None,
            fallback_sha256=fallback.sha256 if fallback is not None else None,
            fallback_size=fallback.size if fallback is not None else None,
        )

    def launch_update_process(self, pending_update: PendingUpdate) -> bool:
        return launch_update_process(pending_update, parent=self.window)

    def launch_pending_update_if_needed(self) -> bool:
        return launch_pending_update_if_needed()

    def schedule_update_for_next_launch(self, result: UpdatePreparation) -> None:
        save_pending_update(self.build_pending_update(result, execute_on_next_launch=True))
        self.window.set_update_status(f"已准备在下次启动时更新到 v{result.target_version}。")
        self.window.append_log(f"已安排在下次启动时更新到 v{result.target_version}。")

    def apply_update_now(self, result: UpdatePreparation) -> None:
        clear_pending_update()
        try:
            launched = self.launch_update_process(self.build_pending_update(result, execute_on_next_launch=False))
        except Exception as exc:
            self.window.set_update_status(str(exc))
            self.window.append_log(str(exc))
            QMessageBox.warning(self.window, "立即更新失败", str(exc))
            return
        if not launched:
            return
        self.window.append_log(f"即将关闭程序并更新到 v{result.target_version}。")
        self.app.quit()

    def show_update_ready_dialog(self, result: UpdatePreparation) -> None:
        asset_label = "增量补丁" if result.asset_kind == "patch" else "全量安装包"
        message_box = QMessageBox(self.window)
        message_box.setWindowTitle("发现新版本")
        message_box.setIcon(QMessageBox.Information)
        message_box.setText(f"新版本 v{result.target_version} 的{asset_label}已准备完成。")
        message_box.setInformativeText("立即更新会关闭当前程序并在完成后自动重启；也可以安排到下次启动时再更新。")
        immediate_button = message_box.addButton("立即更新", QMessageBox.AcceptRole)
        next_launch_button = message_box.addButton("下次启动更新", QMessageBox.ActionRole)
        cancel_button = message_box.addButton("取消", QMessageBox.RejectRole)
        message_box.setDefaultButton(immediate_button)
        message_box.exec()

        clicked_button = message_box.clickedButton()
        if clicked_button is immediate_button:
            self.apply_update_now(result)
            return
        if clicked_button is next_launch_button:
            self.schedule_update_for_next_launch(result)
            return
        if clicked_button is cancel_button:
            self.window.set_update_status("更新包已缓存，可稍后再次检查更新。")
            self.window.append_log("用户取消了本次更新执行，已保留下载缓存。")

    @Slot(str)
    def on_status_message(self, message: str) -> None:
        self.window.set_update_status(message)

    @Slot(object)
    def on_update_finished(self, result: UpdatePreparation) -> None:
        self.window.set_update_status(result.message)
        self.window.append_log(f"更新检查完成：{result.message}")
        if result.status == "up_to_date":
            if self.active_request_is_manual:
                QMessageBox.information(self.window, "检查更新", result.message)
            return

        self.window.append_log(
            f"新版本 v{result.target_version} 已就绪，更新类型：{'增量补丁' if result.asset_kind == 'patch' else '全量安装包'}。"
        )
        self.show_update_ready_dialog(result)

    @Slot(str)
    def on_update_failed(self, message: str) -> None:
        self.window.set_update_status(message)
        self.window.append_log(message)
        if self.active_request_is_manual:
            QMessageBox.warning(self.window, "检查更新失败", message)

    @Slot()
    def on_update_thread_finished(self) -> None:
        self.window.set_update_busy(False)
        self.update_worker = None
        self.update_thread = None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Codex")
    app.setStyle("Fusion")
    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    if launch_pending_update_if_needed():
        return 0

    window = MainWindow(
        window_title=f"{APP_NAME} v{APP_VERSION}",
        initial_theme_name=DEFAULT_THEME_NAME,
    )
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)

    def apply_theme(theme_name: str) -> None:
        normalized_theme_name = normalize_theme_name(theme_name)
        app.setStyleSheet(load_stylesheet(normalized_theme_name))
        window.set_theme(normalized_theme_name)

    window.theme_change_requested.connect(apply_theme)
    apply_theme(DEFAULT_THEME_NAME)
    update_coordinator = UpdateCoordinator(app, window)
    window.show()
    QTimer.singleShot(0, update_coordinator.startup_check)
    return app.exec()
