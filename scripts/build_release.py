from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.app_info import APP_ICON_PARTS, APP_VERSION, BUILD_NAME
from pdf_image_tool.core.versioning import next_release_version


EXCLUDED_MODULES = [
    "IPython",
    "PIL",
    "cv2",
    "datasets",
    "gradio",
    "hf_xet",
    "jinja2",
    "librosa",
    "llvmlite",
    "matplotlib",
    "numba",
    "numpy",
    "onnxruntime",
    "openpyxl",
    "pandas",
    "pyarrow",
    "pythoncom",
    "pywintypes",
    "scipy",
    "sklearn",
    "soundfile",
    "tensorflow",
    "tkinter",
    "tokenizers",
    "torch",
    "torchaudio",
    "torchvision",
    "transformers",
    "win32com",
]


def build_windows_icon(source_png: Path, target_ico: Path) -> Path | None:
    if not source_png.exists():
        return None

    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication, QPixmap

    app = QGuiApplication.instance()
    owns_app = False
    if app is None:
        app = QGuiApplication([])
        owns_app = True

    try:
        pixmap = QPixmap(str(source_png))
        if pixmap.isNull():
            raise RuntimeError(f"无法读取图标源文件：{source_png}")
        target_ico.parent.mkdir(parents=True, exist_ok=True)
        if not pixmap.save(str(target_ico), "ICO"):
            raise RuntimeError(f"无法生成 ICO 图标：{target_ico}")
        return target_ico
    finally:
        if owns_app:
            app.quit()


def main() -> int:
    dist_root = ROOT / "dist"
    dist_root.mkdir(parents=True, exist_ok=True)
    release_version = next_release_version([item.name for item in dist_root.iterdir()], APP_VERSION)
    release_root = dist_root / release_version

    pyinstaller_dist = ROOT / "build" / "pyinstaller-dist"
    pyinstaller_work = ROOT / "build" / "pyinstaller-work"
    spec_root = ROOT / "build" / "spec"
    generated_root = ROOT / "build" / "generated"

    if pyinstaller_dist.exists():
        shutil.rmtree(pyinstaller_dist)
    if pyinstaller_work.exists():
        shutil.rmtree(pyinstaller_work)
    if spec_root.exists():
        shutil.rmtree(spec_root)
    if generated_root.exists():
        shutil.rmtree(generated_root)
    if release_root.exists():
        shutil.rmtree(release_root)

    pyinstaller_dist.mkdir(parents=True, exist_ok=True)
    pyinstaller_work.mkdir(parents=True, exist_ok=True)
    spec_root.mkdir(parents=True, exist_ok=True)
    generated_root.mkdir(parents=True, exist_ok=True)

    icon_source = ROOT.joinpath(*APP_ICON_PARTS)
    icon_target = generated_root / "app_icon.ico"
    generated_icon = build_windows_icon(icon_source, icon_target)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        BUILD_NAME,
        "--paths",
        str(ROOT / "src"),
        "--add-data",
        f"{ROOT / 'assets'};assets",
        "--add-data",
        f"{ROOT / 'logo'};logo",
        "--distpath",
        str(pyinstaller_dist),
        "--workpath",
        str(pyinstaller_work),
        "--specpath",
        str(spec_root),
        str(ROOT / "main.py"),
    ]
    if generated_icon is not None:
        command.extend(["--icon", str(generated_icon)])
    for module_name in EXCLUDED_MODULES:
        command.extend(["--exclude-module", module_name])

    subprocess.run(command, check=True)

    built_app_dir = pyinstaller_dist / BUILD_NAME
    release_root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(built_app_dir, release_root / BUILD_NAME)

    print(release_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
