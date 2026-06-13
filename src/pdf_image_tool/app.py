from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pdf_image_tool.core.app_info import APP_ICON_PARTS, APP_NAME, APP_VERSION
from pdf_image_tool.core.paths import resource_path
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


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Codex")
    app.setStyle("Fusion")
    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

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
    window.show()
    return app.exec()
