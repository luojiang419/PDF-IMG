from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pdf_image_tool.core.app_info import APP_ICON_PARTS, APP_VERSION, BUILD_NAME, release_tag_name


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


def build_macos_icon(source_png: Path, target_icns: Path) -> Path | None:
    if not source_png.exists():
        return None

    iconset_dir = target_icns.with_suffix(".iconset")
    if iconset_dir.exists():
        shutil.rmtree(iconset_dir)
    iconset_dir.mkdir(parents=True, exist_ok=True)
    target_icns.parent.mkdir(parents=True, exist_ok=True)

    for size in (16, 32, 128, 256, 512):
        subprocess.run(
            [
                "sips",
                "-z",
                str(size),
                str(size),
                str(source_png),
                "--out",
                str(iconset_dir / f"icon_{size}x{size}.png"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        retina_size = size * 2
        subprocess.run(
            [
                "sips",
                "-z",
                str(retina_size),
                str(retina_size),
                str(source_png),
                "--out",
                str(iconset_dir / f"icon_{size}x{size}@2x.png"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(target_icns)],
        check=True,
    )
    shutil.rmtree(iconset_dir)
    return target_icns


def build_platform_icon(source_png: Path, generated_root: Path) -> Path | None:
    if sys.platform == "win32":
        return build_windows_icon(source_png, generated_root / "app_icon.ico")
    if sys.platform == "darwin":
        return build_macos_icon(source_png, generated_root / "app_icon.icns")
    return None


def add_data_arg(source: Path, target: str) -> str:
    return f"{source}{os.pathsep}{target}"


def built_output_name() -> str:
    if sys.platform == "darwin":
        return f"{BUILD_NAME}.app"
    return BUILD_NAME


def main() -> int:
    parser = argparse.ArgumentParser(description="构建指定源码版本的发布目录。")
    parser.parse_args()

    dist_root = ROOT / "dist"
    dist_root.mkdir(parents=True, exist_ok=True)
    release_root = dist_root / release_tag_name(APP_VERSION)

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
    generated_icon = build_platform_icon(icon_source, generated_root)

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
        add_data_arg(ROOT / "assets", "assets"),
        "--add-data",
        add_data_arg(ROOT / "logo", "logo"),
        "--add-data",
        add_data_arg(ROOT / "scripts" / "apply_update.ps1", "scripts"),
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

    built_app_dir = pyinstaller_dist / built_output_name()
    release_root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(built_app_dir, release_root / built_app_dir.name)

    print(release_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
