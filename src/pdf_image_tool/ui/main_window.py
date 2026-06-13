from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QDateTime, QSize, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from pdf_image_tool.core.models import BatchResult, PdfTaskResult
from pdf_image_tool.core.preview import list_preview_images
from pdf_image_tool.services.worker import ExtractionWorker


QUEUE_PATH_ROLE = Qt.UserRole
QUEUE_BATCH_ID_ROLE = Qt.UserRole + 1
QUEUE_BATCH_LABEL_ROLE = Qt.UserRole + 2
RESULT_OUTPUT_ROLE = Qt.UserRole


def collect_pdf_paths_from_directory(directory: Path) -> list[Path]:
    pdf_paths: list[Path] = []
    for path in sorted(directory.rglob("*"), key=lambda item: item.as_posix().lower()):
        if path.is_file() and path.suffix.lower() == ".pdf":
            pdf_paths.append(path.resolve())
    return pdf_paths


def extract_local_pdf_paths(urls: list[QUrl]) -> list[Path]:
    pdf_paths: list[Path] = []
    seen: set[str] = set()

    for url in urls:
        if not url.isLocalFile():
            continue
        local_path = Path(url.toLocalFile()).resolve()

        if local_path.is_dir():
            candidates = collect_pdf_paths_from_directory(local_path)
        elif local_path.suffix.lower() == ".pdf":
            candidates = [local_path]
        else:
            candidates = []

        for candidate in candidates:
            normalized = candidate.as_posix().lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            pdf_paths.append(candidate)

    return pdf_paths


def format_file_size(size_in_bytes: int) -> str:
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    if size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    return f"{size_in_bytes / (1024 * 1024):.1f} MB"


def create_theme_toggle_icon(target_theme_name: str) -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    if target_theme_name == "light":
        ray_pen = QPen(QColor("#f59e0b"))
        ray_pen.setWidth(2)
        ray_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(ray_pen)
        for x1, y1, x2, y2 in (
            (12, 2, 12, 5),
            (12, 19, 12, 22),
            (2, 12, 5, 12),
            (19, 12, 22, 12),
            (5, 5, 7, 7),
            (17, 17, 19, 19),
            (5, 19, 7, 17),
            (17, 7, 19, 5),
        ):
            painter.drawLine(x1, y1, x2, y2)

        painter.setPen(QPen(QColor("#f59e0b"), 1))
        painter.setBrush(QColor("#fde68a"))
        painter.drawEllipse(7, 7, 10, 10)
    else:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#6fb7ff"))
        painter.drawEllipse(4, 4, 16, 16)
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.drawEllipse(10, 4, 12, 16)

    painter.end()
    return QIcon(pixmap)


def create_copy_icon() -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#e8fbff"), 1.8))
    painter.setBrush(QColor(0, 0, 0, 0))
    painter.drawRoundedRect(8, 5, 10, 13, 2, 2)
    painter.drawRoundedRect(5, 8, 10, 13, 2, 2)
    painter.end()
    return QIcon(pixmap)


def create_fullscreen_icon() -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#e8fbff"), 2)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    for x1, y1, x2, y2 in (
        (5, 10, 5, 5),
        (5, 5, 10, 5),
        (14, 5, 19, 5),
        (19, 5, 19, 10),
        (19, 14, 19, 19),
        (19, 19, 14, 19),
        (10, 19, 5, 19),
        (5, 19, 5, 14),
    ):
        painter.drawLine(x1, y1, x2, y2)
    painter.end()
    return QIcon(pixmap)


def create_close_icon() -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#e8fbff"), 2)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.drawLine(7, 7, 17, 17)
    painter.drawLine(17, 7, 7, 17)
    painter.end()
    return QIcon(pixmap)


class PdfDropListWidget(QListWidget):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if extract_local_pdf_paths(event.mimeData().urls()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if extract_local_pdf_paths(event.mimeData().urls()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        pdf_paths = extract_local_pdf_paths(event.mimeData().urls())
        if not pdf_paths:
            event.ignore()
            return
        self.files_dropped.emit(pdf_paths)
        event.acceptProposedAction()


class PreviewSurfaceFrame(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.action_bar: QWidget | None = None
        self.has_preview = False
        self.setMouseTracking(True)

    def set_action_bar(self, action_bar: QWidget) -> None:
        self.action_bar = action_bar
        self.action_bar.setVisible(False)

    def set_actions_enabled(self, enabled: bool) -> None:
        self.has_preview = enabled
        if self.action_bar is not None:
            self.action_bar.setVisible(enabled and self.underMouse())

    def enterEvent(self, event) -> None:  # type: ignore[override]
        super().enterEvent(event)
        if self.has_preview and self.action_bar is not None:
            self.action_bar.setVisible(True)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        super().leaveEvent(event)
        if self.action_bar is not None:
            self.action_bar.setVisible(False)


class ClickablePreviewLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton and self.pixmap() is not None and not self.pixmap().isNull():
            self.clicked.emit()
            return
        super().mousePressEvent(event)


class FullscreenPreviewDialog(QDialog):
    preview_index_changed = Signal(int)

    def __init__(self, preview_images: list[Path], start_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview_images = preview_images
        self.preview_index = max(0, min(start_index, len(preview_images) - 1))
        self.preview_source_pixmap: QPixmap | None = None
        self.setWindowTitle("导出预览")
        self.setObjectName("FullscreenPreviewDialog")
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        top_layout = QHBoxLayout()
        self.fullscreen_title_label = QLabel("导出预览")
        self.fullscreen_title_label.setObjectName("FullscreenTitle")
        self.fullscreen_position_label = QLabel("0 / 0")
        self.fullscreen_position_label.setObjectName("PreviewMeta")
        self.fullscreen_position_label.setAlignment(Qt.AlignCenter)
        self.fullscreen_copy_button = QToolButton()
        self.fullscreen_copy_button.setObjectName("PreviewOverlayButton")
        self.fullscreen_copy_button.setIcon(create_copy_icon())
        self.fullscreen_copy_button.setIconSize(QSize(18, 18))
        self.fullscreen_copy_button.setToolTip("复制当前图片到剪贴板")
        self.fullscreen_copy_button.clicked.connect(self.copy_current_image_to_clipboard)
        self.fullscreen_close_button = QToolButton()
        self.fullscreen_close_button.setObjectName("PreviewOverlayButton")
        self.fullscreen_close_button.setIcon(create_close_icon())
        self.fullscreen_close_button.setIconSize(QSize(18, 18))
        self.fullscreen_close_button.setToolTip("关闭全屏预览")
        self.fullscreen_close_button.clicked.connect(self.close)
        top_layout.addWidget(self.fullscreen_title_label)
        top_layout.addStretch(1)
        top_layout.addWidget(self.fullscreen_position_label)
        top_layout.addStretch(1)
        top_layout.addWidget(self.fullscreen_copy_button)
        top_layout.addWidget(self.fullscreen_close_button)
        layout.addLayout(top_layout)

        self.fullscreen_image_label = QLabel("暂无预览")
        self.fullscreen_image_label.setObjectName("FullscreenPreviewSurface")
        self.fullscreen_image_label.setAlignment(Qt.AlignCenter)
        self.fullscreen_image_label.setWordWrap(True)
        layout.addWidget(self.fullscreen_image_label, 1)

        nav_layout = QHBoxLayout()
        self.fullscreen_prev_button = QPushButton("上一张")
        self.fullscreen_prev_button.clicked.connect(self.show_previous_image)
        self.fullscreen_next_button = QPushButton("下一张")
        self.fullscreen_next_button.clicked.connect(self.show_next_image)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.fullscreen_prev_button)
        nav_layout.addWidget(self.fullscreen_next_button)
        nav_layout.addStretch(1)
        layout.addLayout(nav_layout)

        self.prev_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.prev_shortcut.setContext(Qt.WindowShortcut)
        self.prev_shortcut.activated.connect(self.show_previous_image)
        self.next_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.next_shortcut.setContext(Qt.WindowShortcut)
        self.next_shortcut.activated.connect(self.show_next_image)
        self.first_shortcut = QShortcut(QKeySequence(Qt.Key_Home), self)
        self.first_shortcut.setContext(Qt.WindowShortcut)
        self.first_shortcut.activated.connect(lambda: self.show_image_by_index(0))
        self.last_shortcut = QShortcut(QKeySequence(Qt.Key_End), self)
        self.last_shortcut.setContext(Qt.WindowShortcut)
        self.last_shortcut.activated.connect(lambda: self.show_image_by_index(len(self.preview_images) - 1))
        self.close_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.close_shortcut.setContext(Qt.WindowShortcut)
        self.close_shortcut.activated.connect(self.close)

        self.show_image_by_index(self.preview_index, emit_change=False)

    def show_available_fullscreen(self) -> None:
        screen = self.parentWidget().screen() if self.parentWidget() else QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.ActiveWindowFocusReason)

    def show_image_by_index(self, index: int, *, emit_change: bool = True) -> None:
        if index < 0 or index >= len(self.preview_images):
            return

        preview_image_path = self.preview_images[index]
        pixmap = QPixmap(str(preview_image_path))
        if pixmap.isNull():
            self.fullscreen_image_label.setText("预览图片加载失败。")
            return

        self.preview_index = index
        self.preview_source_pixmap = pixmap
        self.fullscreen_position_label.setText(f"{index + 1} / {len(self.preview_images)}")
        self.fullscreen_title_label.setText(preview_image_path.name)
        self.fullscreen_prev_button.setEnabled(index > 0)
        self.fullscreen_next_button.setEnabled(index < len(self.preview_images) - 1)
        self.render_current_pixmap()
        if emit_change:
            self.preview_index_changed.emit(index)

    def render_current_pixmap(self) -> None:
        if self.preview_source_pixmap is None:
            return

        available_width = max(240, self.fullscreen_image_label.width() - 32)
        available_height = max(240, self.fullscreen_image_label.height() - 32)
        scaled_pixmap = self.preview_source_pixmap.scaled(
            available_width,
            available_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.fullscreen_image_label.setText("")
        self.fullscreen_image_label.setPixmap(scaled_pixmap)

    def show_previous_image(self) -> None:
        if self.preview_index <= 0:
            return
        self.show_image_by_index(self.preview_index - 1)

    def show_next_image(self) -> None:
        if self.preview_index >= len(self.preview_images) - 1:
            return
        self.show_image_by_index(self.preview_index + 1)

    def copy_current_image_to_clipboard(self) -> None:
        if self.preview_source_pixmap is None:
            return
        QApplication.clipboard().setPixmap(self.preview_source_pixmap)
        self.fullscreen_position_label.setText(f"已复制 | {self.preview_index + 1} / {len(self.preview_images)}")

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        if event.key() == Qt.Key_Left:
            self.show_previous_image()
            return
        if event.key() == Qt.Key_Right:
            self.show_next_image()
            return
        if event.key() == Qt.Key_Home:
            self.show_image_by_index(0)
            return
        if event.key() == Qt.Key_End:
            self.show_image_by_index(len(self.preview_images) - 1)
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.render_current_pixmap()


class MainWindow(QMainWindow):
    theme_change_requested = Signal(str)

    def __init__(self, window_title: str, initial_theme_name: str = "dark") -> None:
        super().__init__()
        self.setWindowTitle(window_title)
        self.resize(1280, 800)
        self.setMinimumSize(960, 640)
        self.current_theme_name = initial_theme_name if initial_theme_name == "light" else "dark"

        self.pdf_paths: list[Path] = []
        self.output_dir: Path | None = None
        self.last_output_dir: Path | None = None
        self.active_output_root: Path | None = None
        self.active_run_mode = "advanced"
        self.worker_thread: QThread | None = None
        self.worker: ExtractionWorker | None = None
        self.is_running = False
        self.queue_items: dict[str, QListWidgetItem] = {}
        self.quick_queue_items: dict[str, QListWidgetItem] = {}
        self.source_batch_labels: dict[str, str] = {}
        self.import_batch_counter = 0
        self.preview_images: list[Path] = []
        self.preview_index = -1
        self.preview_source_pixmap: QPixmap | None = None
        self.preview_image_path: Path | None = None
        self.fullscreen_preview_dialog: FullscreenPreviewDialog | None = None
        self.preview_prev_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.preview_prev_shortcut.setContext(Qt.WindowShortcut)
        self.preview_prev_shortcut.activated.connect(self.show_previous_preview_image)
        self.preview_next_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.preview_next_shortcut.setContext(Qt.WindowShortcut)
        self.preview_next_shortcut.activated.connect(self.show_next_preview_image)
        self.preview_first_shortcut = QShortcut(QKeySequence(Qt.Key_Home), self)
        self.preview_first_shortcut.setContext(Qt.WindowShortcut)
        self.preview_first_shortcut.activated.connect(self.show_first_preview_image)
        self.preview_last_shortcut = QShortcut(QKeySequence(Qt.Key_End), self)
        self.preview_last_shortcut.setContext(Qt.WindowShortcut)
        self.preview_last_shortcut.activated.connect(self.show_last_preview_image)

        self._build_ui()
        self.set_theme(self.current_theme_name)
        self.clear_preview()
        self.refresh_controls()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        root_layout.addWidget(self._create_header(), 0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        self.tabs.addTab(self._create_quick_tab(), "快速提取")
        self.tabs.addTab(self._create_advanced_tab(), "进阶操作")
        self.tabs.addTab(self._create_log_tab(), "运行日志")
        self.tabs.addTab(self._create_settings_tab(), "设置")
        root_layout.addWidget(self.tabs, 1)

        self.setCentralWidget(root)

    def _create_card(self, title: str, body_layout: QVBoxLayout | QHBoxLayout | QGridLayout) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        layout.addWidget(title_label)
        layout.addLayout(body_layout)
        return card

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HeaderCard")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(6)

        title = QLabel("PDF 图片提取工具")
        title.setObjectName("Title")
        subtitle = QLabel("离线提取 PDF 内嵌图片，快速模式一步完成，进阶模式管理批量队列。")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        layout.addLayout(title_layout, 1)

        self.theme_toggle_button = QToolButton()
        self.theme_toggle_button.setObjectName("ThemeToggleButton")
        self.theme_toggle_button.setCursor(Qt.PointingHandCursor)
        self.theme_toggle_button.setFixedSize(42, 42)
        self.theme_toggle_button.setIconSize(QSize(20, 20))
        self.theme_toggle_button.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_toggle_button, 0, Qt.AlignTop | Qt.AlignRight)
        return header

    def _create_quick_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        quick_layout = QVBoxLayout()
        quick_layout.setSpacing(12)

        self.quick_status_label = QLabel("导入 PDF 后即可开始提取。")
        self.quick_status_label.setObjectName("Hint")
        self.quick_status_label.setWordWrap(True)
        quick_layout.addWidget(self.quick_status_label)

        self.quick_file_list = PdfDropListWidget()
        self.quick_file_list.setObjectName("QuickFileList")
        self.quick_file_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.quick_file_list.setTextElideMode(Qt.ElideMiddle)
        self.quick_file_list.files_dropped.connect(self.on_pdf_files_dropped)
        quick_layout.addWidget(self.quick_file_list, 1)

        quick_actions = QHBoxLayout()
        quick_actions.setSpacing(10)
        self.quick_add_files_button = QPushButton("导入 PDF")
        self.quick_add_files_button.clicked.connect(self.choose_pdf_files)
        self.quick_start_button = QPushButton("开始提取")
        self.quick_start_button.setObjectName("PrimaryButton")
        self.quick_start_button.clicked.connect(self.start_quick_extraction)
        self.quick_open_output_button = QPushButton("打开导出文件夹")
        self.quick_open_output_button.clicked.connect(self.open_quick_output_directory)
        quick_actions.addWidget(self.quick_add_files_button)
        quick_actions.addWidget(self.quick_start_button)
        quick_actions.addWidget(self.quick_open_output_button)
        quick_layout.addLayout(quick_actions)

        self.quick_progress_bar = QProgressBar()
        self.quick_progress_bar.setRange(0, 100)
        self.quick_progress_bar.setValue(0)
        self.quick_progress_bar.setFormat("等待开始")
        quick_layout.addWidget(self.quick_progress_bar)

        layout.addWidget(self._create_card("快速提取", quick_layout), 1)
        return page

    def _create_advanced_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(14)

        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        queue_layout = QVBoxLayout()
        queue_layout.setSpacing(10)

        self.queue_count_label = QLabel("当前未添加 PDF")
        self.queue_count_label.setObjectName("Hint")
        self.queue_count_label.setWordWrap(True)
        queue_layout.addWidget(self.queue_count_label)

        self.file_list = PdfDropListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setTextElideMode(Qt.ElideMiddle)
        self.file_list.files_dropped.connect(self.on_pdf_files_dropped)
        self.file_list.itemSelectionChanged.connect(self.refresh_controls)
        queue_layout.addWidget(self.file_list, 1)

        self.queue_drop_hint_label = QLabel("支持将 PDF 文件或文件夹直接拖拽到列表中。")
        self.queue_drop_hint_label.setObjectName("Hint")
        self.queue_drop_hint_label.setWordWrap(True)
        queue_layout.addWidget(self.queue_drop_hint_label)

        import_buttons = QHBoxLayout()
        self.add_files_button = QPushButton("添加 PDF")
        self.add_files_button.clicked.connect(self.choose_pdf_files)
        self.add_folder_button = QPushButton("添加文件夹")
        self.add_folder_button.clicked.connect(self.choose_pdf_directory)
        import_buttons.addWidget(self.add_files_button)
        import_buttons.addWidget(self.add_folder_button)
        queue_layout.addLayout(import_buttons)

        manage_buttons = QHBoxLayout()
        self.remove_batch_button = QPushButton("移除同批来源")
        self.remove_batch_button.clicked.connect(self.remove_selected_source_batches)
        self.remove_files_button = QPushButton("移除选中")
        self.remove_files_button.clicked.connect(self.remove_selected_pdf_files)
        self.clear_files_button = QPushButton("清空列表")
        self.clear_files_button.clicked.connect(self.clear_pdf_files)
        manage_buttons.addWidget(self.remove_batch_button)
        manage_buttons.addWidget(self.remove_files_button)
        manage_buttons.addWidget(self.clear_files_button)
        queue_layout.addLayout(manage_buttons)

        self.start_button = QPushButton("开始批量提取")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.start_extraction)
        queue_layout.addWidget(self.start_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("等待开始")
        self.advanced_progress_bar = self.progress_bar
        queue_layout.addWidget(self.advanced_progress_bar)

        self.action_hint_label = QLabel("进阶操作会使用“设置”里的输出目录。")
        self.action_hint_label.setObjectName("Hint")
        self.action_hint_label.setWordWrap(True)
        queue_layout.addWidget(self.action_hint_label)

        left_column.addWidget(self._create_card("文件队列", queue_layout), 1)
        layout.addLayout(left_column, 5)

        right_column = QVBoxLayout()
        right_column.setSpacing(12)

        result_layout = QVBoxLayout()
        result_layout.setSpacing(10)
        result_meta_layout = QHBoxLayout()
        self.result_hint_label = QLabel("双击结果行可直接打开该 PDF 的导出目录。")
        self.result_hint_label.setObjectName("Hint")
        self.result_hint_label.setWordWrap(True)
        result_meta_layout.addWidget(self.result_hint_label)
        result_meta_layout.addStretch(1)
        self.open_result_button = QPushButton("打开选中结果目录")
        self.open_result_button.clicked.connect(self.open_selected_result_directory)
        result_meta_layout.addWidget(self.open_result_button)
        result_layout.addLayout(result_meta_layout)

        self.result_table = QTableWidget(0, 5)
        self.result_table.setHorizontalHeaderLabels(["PDF", "提取成功", "格式转换", "跳过", "状态"])
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.result_table.setTextElideMode(Qt.ElideMiddle)
        self.result_table.itemSelectionChanged.connect(self.on_result_selection_changed)
        self.result_table.itemDoubleClicked.connect(self.open_selected_result_directory)
        self.result_table.verticalHeader().setVisible(False)
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column_index in range(1, 5):
            header.setSectionResizeMode(column_index, QHeaderView.ResizeToContents)
        result_layout.addWidget(self.result_table, 1)
        result_card = self._create_card("处理结果", result_layout)

        preview_layout = QVBoxLayout()
        preview_layout.setSpacing(10)
        self.preview_hint_label = QLabel("选中结果后，可用按钮、左右方向键或 Home/End 切换导出图片预览。")
        self.preview_hint_label.setObjectName("Hint")
        self.preview_hint_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_hint_label)

        preview_nav_layout = QHBoxLayout()
        self.preview_prev_button = QPushButton("上一张")
        self.preview_prev_button.clicked.connect(self.show_previous_preview_image)
        self.preview_position_label = QLabel("0 / 0")
        self.preview_position_label.setObjectName("PreviewMeta")
        self.preview_position_label.setAlignment(Qt.AlignCenter)
        self.preview_next_button = QPushButton("下一张")
        self.preview_next_button.clicked.connect(self.show_next_preview_image)
        preview_nav_layout.addWidget(self.preview_prev_button)
        preview_nav_layout.addWidget(self.preview_position_label, 1)
        preview_nav_layout.addWidget(self.preview_next_button)
        preview_layout.addLayout(preview_nav_layout)

        self.preview_surface = PreviewSurfaceFrame()
        self.preview_surface.setObjectName("PreviewSurfaceContainer")
        preview_surface_layout = QGridLayout(self.preview_surface)
        preview_surface_layout.setContentsMargins(0, 0, 0, 0)
        preview_surface_layout.setSpacing(0)

        self.preview_image_label = ClickablePreviewLabel("暂无预览")
        self.preview_image_label.setObjectName("PreviewSurface")
        self.preview_image_label.setAlignment(Qt.AlignCenter)
        self.preview_image_label.setWordWrap(True)
        self.preview_image_label.setMinimumHeight(80)
        self.preview_image_label.clicked.connect(self.open_fullscreen_preview)
        preview_surface_layout.addWidget(self.preview_image_label, 0, 0)

        self.preview_action_bar = QWidget()
        self.preview_action_bar.setObjectName("PreviewOverlayActions")
        preview_action_layout = QHBoxLayout(self.preview_action_bar)
        preview_action_layout.setContentsMargins(6, 6, 6, 6)
        preview_action_layout.setSpacing(6)
        self.preview_copy_button = QToolButton()
        self.preview_copy_button.setObjectName("PreviewOverlayButton")
        self.preview_copy_button.setIcon(create_copy_icon())
        self.preview_copy_button.setIconSize(QSize(18, 18))
        self.preview_copy_button.setToolTip("复制当前图片到剪贴板")
        self.preview_copy_button.clicked.connect(self.copy_current_preview_image)
        self.preview_fullscreen_button = QToolButton()
        self.preview_fullscreen_button.setObjectName("PreviewOverlayButton")
        self.preview_fullscreen_button.setIcon(create_fullscreen_icon())
        self.preview_fullscreen_button.setIconSize(QSize(18, 18))
        self.preview_fullscreen_button.setToolTip("全屏显示导出预览")
        self.preview_fullscreen_button.clicked.connect(self.open_fullscreen_preview)
        preview_action_layout.addWidget(self.preview_copy_button)
        preview_action_layout.addWidget(self.preview_fullscreen_button)
        preview_surface_layout.addWidget(
            self.preview_action_bar,
            0,
            0,
            Qt.AlignRight | Qt.AlignBottom,
        )
        self.preview_surface.set_action_bar(self.preview_action_bar)
        preview_layout.addWidget(self.preview_surface, 1)
        self.preview_meta_label = QLabel("等待选择结果")
        self.preview_meta_label.setObjectName("PreviewMeta")
        self.preview_meta_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_meta_label)
        right_column.addWidget(self._create_card("导出预览", preview_layout), 1)
        right_column.addWidget(result_card, 1)

        layout.addLayout(right_column, 7)
        return page

    def _create_log_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        log_layout = QVBoxLayout()
        log_layout.setSpacing(10)
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output, 1)
        layout.addWidget(self._create_card("运行日志", log_layout), 1)
        return page

    def _create_settings_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        output_layout = QVBoxLayout()
        output_layout.setSpacing(10)
        self.settings_output_hint_label = QLabel("进阶操作默认输出到这里；快速提取每次都会询问保存位置。")
        self.settings_output_hint_label.setObjectName("Hint")
        self.settings_output_hint_label.setWordWrap(True)
        output_layout.addWidget(self.settings_output_hint_label)

        self.output_line_edit = QLineEdit()
        self.output_line_edit.setReadOnly(True)
        self.output_line_edit.setPlaceholderText("请选择进阶操作输出根目录")
        output_layout.addWidget(self.output_line_edit)

        output_button_layout = QHBoxLayout()
        self.choose_output_button = QPushButton("选择输出目录")
        self.choose_output_button.clicked.connect(self.choose_output_directory)
        self.open_output_button = QPushButton("打开输出目录")
        self.open_output_button.clicked.connect(self.open_output_directory)
        output_button_layout.addWidget(self.choose_output_button)
        output_button_layout.addWidget(self.open_output_button)
        output_button_layout.addStretch(1)
        output_layout.addLayout(output_button_layout)

        layout.addWidget(self._create_card("输出目录", output_layout), 0)
        layout.addStretch(1)
        return page

    def refresh_controls(self) -> None:
        has_files = bool(self.pdf_paths)
        has_output = self.output_dir is not None
        can_start_advanced = has_files and has_output and not self.is_running
        can_start_quick = has_files and not self.is_running
        has_selected_queue_items = bool(self.file_list.selectedItems())
        has_selected_result_output = self.selected_result_output_dir() is not None
        has_preview_image = self.preview_index >= 0 and self.preview_image_path is not None

        self.quick_add_files_button.setEnabled(not self.is_running)
        self.quick_start_button.setEnabled(can_start_quick)
        self.quick_open_output_button.setEnabled(self.last_output_dir is not None and not self.is_running)
        self.clear_files_button.setEnabled(has_files and not self.is_running)
        self.add_files_button.setEnabled(not self.is_running)
        self.add_folder_button.setEnabled(not self.is_running)
        self.remove_batch_button.setEnabled(has_selected_queue_items and not self.is_running)
        self.remove_files_button.setEnabled(has_selected_queue_items and not self.is_running)
        self.choose_output_button.setEnabled(not self.is_running)
        self.start_button.setEnabled(can_start_advanced)
        self.open_output_button.setEnabled(has_output and not self.is_running)
        self.open_result_button.setEnabled(has_selected_result_output and not self.is_running)
        self.preview_prev_button.setEnabled(not self.is_running and self.preview_index > 0)
        self.preview_next_button.setEnabled(
            not self.is_running and 0 <= self.preview_index < len(self.preview_images) - 1
        )
        self.preview_copy_button.setEnabled(has_preview_image)
        self.preview_fullscreen_button.setEnabled(has_preview_image)
        self.preview_image_label.setCursor(Qt.PointingHandCursor if has_preview_image else Qt.ArrowCursor)
        self.preview_surface.set_actions_enabled(has_preview_image)

        queue_text = "PDF 队列已准备" if has_files else "当前未添加 PDF"
        self.queue_count_label.setText(queue_text)
        self.quick_status_label.setText(
            "处理中，请等待当前提取完成。"
            if self.is_running
            else ("PDF 已导入，可以开始提取。" if has_files else "导入 PDF 后即可开始提取。")
        )
        self.action_hint_label.setText(
            "处理中请勿修改队列，日志会实时更新每个 PDF 的状态。"
            if self.is_running
            else "进阶操作会使用“设置”里的输出目录。"
        )

    def set_theme(self, theme_name: str) -> None:
        self.current_theme_name = theme_name if theme_name == "light" else "dark"
        target_theme_name = "dark" if self.current_theme_name == "light" else "light"
        target_theme_label = "深色主题" if target_theme_name == "dark" else "浅色主题"
        self.theme_toggle_button.setIcon(create_theme_toggle_icon(target_theme_name))
        self.theme_toggle_button.setToolTip(f"切换到{target_theme_label}")
        self.theme_toggle_button.setStatusTip(f"切换到{target_theme_label}")

    def toggle_theme(self) -> None:
        next_theme_name = "light" if self.current_theme_name == "dark" else "dark"
        self.theme_change_requested.emit(next_theme_name)

    def copy_current_preview_image(self) -> None:
        if self.preview_source_pixmap is None or self.preview_image_path is None:
            return
        QApplication.clipboard().setPixmap(self.preview_source_pixmap)
        self.preview_meta_label.setText(f"已复制到系统粘贴板：{self.preview_image_path.name}")
        self.append_log(f"已复制预览图片到系统粘贴板：{self.preview_image_path.name}")

    def open_fullscreen_preview(self) -> None:
        if not self.preview_images or self.preview_index < 0:
            return
        dialog = FullscreenPreviewDialog(self.preview_images, self.preview_index, self)
        dialog.preview_index_changed.connect(self.show_preview_image_by_index)
        dialog.finished.connect(lambda _result: setattr(self, "fullscreen_preview_dialog", None))
        self.fullscreen_preview_dialog = dialog
        dialog.show_available_fullscreen()

    def choose_pdf_files(self) -> None:
        start_dir = str(Path.home() / "Desktop")
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择 PDF 文件",
            start_dir,
            "PDF Files (*.pdf)",
        )
        if not file_paths:
            return
        self.add_pdf_paths([Path(file_path) for file_path in file_paths], source="文件选择")

    def choose_pdf_directory(self) -> None:
        start_dir = str(Path.home() / "Desktop")
        directory = QFileDialog.getExistingDirectory(self, "选择包含 PDF 的文件夹", start_dir)
        if not directory:
            return

        folder_path = Path(directory)
        pdf_paths = collect_pdf_paths_from_directory(folder_path)
        if not pdf_paths:
            self.append_log(f"所选文件夹中未发现 PDF 文件：{folder_path}")
            QMessageBox.information(self, "未发现 PDF", "所选文件夹及其子文件夹中未发现 PDF 文件。")
            return

        self.add_pdf_paths(pdf_paths, source=f"文件夹选择（{folder_path.name}）")

    def create_import_batch(self, source: str) -> tuple[str, str]:
        self.import_batch_counter += 1
        batch_id = f"batch-{self.import_batch_counter:04d}"
        batch_label = f"第{self.import_batch_counter:02d}批：{source}"
        self.source_batch_labels[batch_id] = batch_label
        return batch_id, batch_label

    def add_pdf_paths(self, pdf_paths: list[Path], *, source: str) -> int:
        added_count = 0
        skipped_count = 0
        existing = {self.pdf_path_key(path) for path in self.pdf_paths}
        batch_id, batch_label = self.create_import_batch(source)

        for pdf_path in pdf_paths:
            resolved_path = pdf_path.resolve()
            key = self.pdf_path_key(resolved_path)
            if resolved_path.suffix.lower() != ".pdf" or key in existing:
                skipped_count += 1
                continue

            existing.add(key)
            added_count += 1
            self.pdf_paths.append(resolved_path)
            item = QListWidgetItem(resolved_path.name)
            item.setToolTip(f"{resolved_path.as_posix()}\n来源批次：{batch_label}")
            item.setData(QUEUE_PATH_ROLE, key)
            item.setData(QUEUE_BATCH_ID_ROLE, batch_id)
            item.setData(QUEUE_BATCH_LABEL_ROLE, batch_label)
            self.file_list.addItem(item)
            self.queue_items[key] = item

        if added_count == 0:
            self.source_batch_labels.pop(batch_id, None)
        self.rebuild_quick_file_list()
        if added_count:
            self.append_log(f"已通过{source}新增 PDF 文件。")
        if skipped_count:
            self.append_log(f"{source}中有文件未加入队列，原因可能是重复或不是 PDF。")
        self.refresh_controls()
        return added_count

    def rebuild_quick_file_list(self) -> None:
        self.quick_file_list.clear()
        self.quick_queue_items.clear()
        for pdf_path in self.pdf_paths:
            key = self.pdf_path_key(pdf_path)
            item = QListWidgetItem(pdf_path.name)
            item.setToolTip(pdf_path.as_posix())
            item.setData(QUEUE_PATH_ROLE, key)
            self.quick_file_list.addItem(item)
            self.quick_queue_items[key] = item

    def on_pdf_files_dropped(self, pdf_paths: list[Path]) -> None:
        self.add_pdf_paths(pdf_paths, source="拖拽导入")

    def selected_queue_batch_ids(self) -> set[str]:
        return {
            item.data(QUEUE_BATCH_ID_ROLE)
            for item in self.file_list.selectedItems()
            if item.data(QUEUE_BATCH_ID_ROLE)
        }

    def remove_queue_keys(self, remove_keys: set[str]) -> int:
        if not remove_keys:
            return 0

        self.pdf_paths = [path for path in self.pdf_paths if self.pdf_path_key(path) not in remove_keys]
        removed_count = 0
        for index in range(self.file_list.count() - 1, -1, -1):
            item = self.file_list.item(index)
            if item.data(QUEUE_PATH_ROLE) in remove_keys:
                self.file_list.takeItem(index)
                removed_count += 1

        for key in remove_keys:
            self.queue_items.pop(key, None)

        active_batch_ids = {
            self.file_list.item(index).data(QUEUE_BATCH_ID_ROLE)
            for index in range(self.file_list.count())
            if self.file_list.item(index).data(QUEUE_BATCH_ID_ROLE)
        }
        self.source_batch_labels = {
            batch_id: label
            for batch_id, label in self.source_batch_labels.items()
            if batch_id in active_batch_ids
        }
        self.rebuild_quick_file_list()
        self.refresh_controls()
        return removed_count

    def remove_selected_source_batches(self) -> None:
        if self.is_running:
            return

        batch_ids = self.selected_queue_batch_ids()
        if not batch_ids:
            return

        batch_labels = [
            self.source_batch_labels.get(batch_id, batch_id)
            for batch_id in sorted(batch_ids)
        ]
        remove_keys = {
            self.file_list.item(index).data(QUEUE_PATH_ROLE)
            for index in range(self.file_list.count())
            if self.file_list.item(index).data(QUEUE_BATCH_ID_ROLE) in batch_ids
        }
        removed_count = self.remove_queue_keys(remove_keys)

        if len(batch_labels) == 1:
            self.append_log(f"已移除来源批次“{batch_labels[0]}”中的 PDF 文件。")
            return
        self.append_log(f"已移除 {len(batch_labels)} 个来源批次，共 {removed_count} 个 PDF 文件。")

    def remove_selected_pdf_files(self) -> None:
        if self.is_running:
            return
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return

        remove_keys = {item.data(QUEUE_PATH_ROLE) for item in selected_items}
        removed_count = self.remove_queue_keys(remove_keys)
        self.append_log("已从队列移除选中的 PDF 文件。")
        if removed_count != len(remove_keys):
            self.append_log("有部分选中项未成功移除，请检查队列状态。")

    def clear_pdf_files(self) -> None:
        self.pdf_paths.clear()
        self.queue_items.clear()
        self.quick_queue_items.clear()
        self.source_batch_labels.clear()
        self.import_batch_counter = 0
        self.file_list.clear()
        self.quick_file_list.clear()
        self.result_table.setRowCount(0)
        self.clear_preview()
        self.append_log("已清空 PDF 队列。")
        self.refresh_controls()

    def choose_output_directory(self) -> None:
        start_dir = str(Path.home() / "Desktop")
        directory = QFileDialog.getExistingDirectory(self, "选择进阶操作输出根目录", start_dir)
        if not directory:
            return
        self.output_dir = Path(directory)
        self.output_line_edit.setText(self.output_dir.as_posix())
        self.append_log(f"进阶操作输出根目录已设置为：{self.output_dir}")
        self.refresh_controls()

    def open_output_directory(self) -> None:
        if not self.output_dir:
            return
        os.startfile(self.output_dir)  # type: ignore[attr-defined]

    def open_quick_output_directory(self) -> None:
        if not self.last_output_dir:
            return
        os.startfile(self.last_output_dir)  # type: ignore[attr-defined]

    def open_selected_result_directory(self, *_args: object) -> None:
        output_dir = self.selected_result_output_dir()
        if output_dir is None:
            return
        os.startfile(output_dir)  # type: ignore[attr-defined]

    def start_quick_extraction(self) -> None:
        if self.is_running:
            return
        if not self.pdf_paths:
            QMessageBox.warning(self, "无法开始", "请先导入至少一个 PDF。")
            return

        start_dir = str(Path.home() / "Desktop")
        directory = QFileDialog.getExistingDirectory(self, "选择图片保存位置", start_dir)
        if not directory:
            return
        self.active_run_mode = "quick"
        self._begin_extraction(Path(directory))

    def start_extraction(self) -> None:
        if self.is_running:
            return
        if not self.pdf_paths:
            QMessageBox.warning(self, "无法开始", "请先选择至少一个 PDF。")
            return
        if self.output_dir is None:
            QMessageBox.warning(self, "无法开始", "请先在“设置”中选择输出目录。")
            return

        self.active_run_mode = "advanced"
        self._begin_extraction(self.output_dir)

    def _begin_extraction(self, output_root: Path) -> None:
        self.is_running = True
        self.active_output_root = output_root
        self.last_output_dir = None
        self.clear_preview("正在等待新的导出结果。")
        self.result_table.setRowCount(0)
        self.set_progress(0, "准备处理中...")

        for pdf_path in self.pdf_paths:
            self.set_queue_item_status(pdf_path, "等待", QColor("#9edce7"))

        self.worker_thread = QThread(self)
        self.worker = ExtractionWorker(self.pdf_paths.copy(), output_root)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress_changed.connect(self.on_progress_changed)
        self.worker.log_message.connect(self.append_log)
        self.worker.task_finished.connect(self.on_task_finished)
        self.worker.batch_finished.connect(self.on_batch_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.on_worker_thread_finished)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.append_log("开始批量提取图片。")
        self.refresh_controls()
        self.worker_thread.start()

    def set_progress(self, value: int, text: str) -> None:
        self.quick_progress_bar.setValue(value)
        self.quick_progress_bar.setFormat(text)
        self.advanced_progress_bar.setValue(value)
        self.advanced_progress_bar.setFormat(text)

    @Slot(int, int)
    def on_progress_changed(self, current: int, total: int) -> None:
        if total <= 0:
            self.set_progress(0, "等待开始")
            return
        percent = int(current / total * 100)
        self.set_progress(percent, f"已完成 {current}/{total} 个 PDF")

    @Slot(object)
    def on_task_finished(self, result: PdfTaskResult) -> None:
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)
        values = [
            result.pdf_path.name,
            str(result.extracted_count),
            str(result.converted_count),
            str(result.skipped_count),
            result.error_message or result.status_label,
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 0 and result.output_dir is not None:
                item.setData(RESULT_OUTPUT_ROLE, result.output_dir.as_posix())
            if column == 4 and result.error_message:
                item.setForeground(QColor("#ff9a99"))
            self.result_table.setItem(row, column, item)

        status_color = QColor("#8de8a4") if result.is_success else QColor("#ff9a99")
        self.set_queue_item_status(result.pdf_path, result.status_label, status_color)
        if self.selected_result_output_dir() is None and result.output_dir is not None and result.extracted_count > 0:
            self.result_table.selectRow(row)
        self.refresh_controls()

    @Slot(object)
    def on_batch_finished(self, batch_result: BatchResult) -> None:
        self.set_progress(100, f"全部完成：成功 {batch_result.success_files} / {batch_result.total_files}")
        output_dirs = [item.output_dir for item in batch_result.items if item.output_dir is not None]
        self.last_output_dir = output_dirs[0] if len(output_dirs) == 1 else self.active_output_root
        self.append_log(
            f"批量处理结束：导出 {batch_result.total_images} 张图片，转换 {batch_result.total_converted} 张，失败 {batch_result.failed_files} 个 PDF。"
        )
        if self.active_run_mode == "quick":
            QMessageBox.information(self, "提取完成", "PDF 图片提取已完成。")
        self.refresh_controls()

    @Slot()
    def on_worker_thread_finished(self) -> None:
        self.worker = None
        self.worker_thread = None
        self.is_running = False
        self.refresh_controls()

    @Slot()
    def on_result_selection_changed(self) -> None:
        self.refresh_controls()
        self.update_preview_from_selection()

    def update_stat_cards(
        self,
        *,
        total_files: int | None = None,
        success_files: int | None = None,
        total_images: int | None = None,
        converted_images: int | None = None,
    ) -> None:
        return

    def append_log(self, message: str) -> None:
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.log_output.appendPlainText(f"[{timestamp}] {message}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def set_queue_item_status(self, pdf_path: Path, status: str, color: QColor) -> None:
        key = self.pdf_path_key(pdf_path)
        item = self.queue_items.get(key)
        if item is not None:
            item.setText(f"[{status}] {pdf_path.name}")
            item.setForeground(color)
        quick_item = self.quick_queue_items.get(key)
        if quick_item is not None:
            quick_item.setText(f"[{status}] {pdf_path.name}")
            quick_item.setForeground(color)

    def clear_preview(self, message: str = "选中一条成功结果后，这里会显示第一张导出图片。") -> None:
        self.preview_images = []
        self.preview_index = -1
        self.preview_source_pixmap = None
        self.preview_image_path = None
        self.preview_image_label.clear()
        self.preview_image_label.setText(message)
        self.preview_position_label.setText("0 / 0")
        self.preview_meta_label.setText("等待选择结果")
        self.refresh_controls()

    def update_preview_from_selection(self) -> None:
        output_dir = self.selected_result_output_dir()
        if output_dir is None:
            self.clear_preview()
            return

        self.preview_images = list_preview_images(output_dir)
        if not self.preview_images:
            self.clear_preview("该结果目录中暂无可预览图片。")
            self.preview_meta_label.setText(output_dir.name)
            return

        self.show_preview_image_by_index(0)

    def show_previous_preview_image(self) -> None:
        if self.preview_index <= 0:
            return
        self.show_preview_image_by_index(self.preview_index - 1)

    def show_next_preview_image(self) -> None:
        if self.preview_index < 0 or self.preview_index >= len(self.preview_images) - 1:
            return
        self.show_preview_image_by_index(self.preview_index + 1)

    def show_first_preview_image(self) -> None:
        if not self.preview_images:
            return
        self.show_preview_image_by_index(0)

    def show_last_preview_image(self) -> None:
        if not self.preview_images:
            return
        self.show_preview_image_by_index(len(self.preview_images) - 1)

    def show_preview_image_by_index(self, index: int) -> None:
        if index < 0 or index >= len(self.preview_images):
            return

        preview_image_path = self.preview_images[index]
        pixmap = QPixmap(str(preview_image_path))
        if pixmap.isNull():
            self.clear_preview("预览图片加载失败。")
            self.preview_meta_label.setText(preview_image_path.name)
            return

        self.preview_index = index
        self.preview_source_pixmap = pixmap
        self.preview_image_path = preview_image_path
        self.render_preview_pixmap()
        self.preview_position_label.setText(f"{index + 1} / {len(self.preview_images)}")
        self.preview_meta_label.setText(
            f"{preview_image_path.name} | {pixmap.width()} x {pixmap.height()} | {format_file_size(preview_image_path.stat().st_size)}"
        )
        self.refresh_controls()

    def render_preview_pixmap(self) -> None:
        if self.preview_source_pixmap is None:
            return

        available_width = max(120, self.preview_image_label.width() - 24)
        available_height = max(120, self.preview_image_label.height() - 24)
        scaled_pixmap = self.preview_source_pixmap.scaled(
            available_width,
            available_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_image_label.setText("")
        self.preview_image_label.setPixmap(scaled_pixmap)

    def selected_result_output_dir(self) -> Path | None:
        selected_items = self.result_table.selectedItems()
        if not selected_items:
            return None
        first_item = self.result_table.item(selected_items[0].row(), 0)
        if first_item is None:
            return None
        output_dir = first_item.data(RESULT_OUTPUT_ROLE)
        if not output_dir:
            return None
        return Path(output_dir)

    def pdf_path_key(self, pdf_path: Path) -> str:
        return pdf_path.resolve().as_posix().lower()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.render_preview_pixmap()
