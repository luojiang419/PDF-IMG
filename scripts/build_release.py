from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
import os

from PyInstaller.building import makespec


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


def built_output_name() -> str:
    if sys.platform == "darwin":
        return f"{BUILD_NAME}.app"
    return BUILD_NAME


def bundle_info_plist_fragment() -> str:
    return (
        "    info_plist={"
        f"'CFBundleShortVersionString': {APP_VERSION!r}, "
        f"'CFBundleVersion': {APP_VERSION!r}"
        "},\n"
    )


def inject_macos_bundle_info_plist(spec_file: Path) -> None:
    lines = spec_file.read_text(encoding="utf-8").splitlines(keepends=True)
    in_bundle_block = False
    for index, line in enumerate(lines):
        if line.startswith("app = BUNDLE("):
            in_bundle_block = True
            continue
        if in_bundle_block and line.startswith("    icon="):
            lines.insert(index + 1, bundle_info_plist_fragment())
            spec_file.write_text("".join(lines), encoding="utf-8")
            return
        if in_bundle_block and line.strip() == ")":
            break

    raise RuntimeError(f"未能在 spec 中注入 macOS bundle 版本信息：{spec_file}")


def build_release_spec(
    *,
    spec_root: Path,
    generated_icon: Path | None,
) -> Path:
    spec_path = Path(
        makespec.main(
            [str(ROOT / "main.py")],
            name=BUILD_NAME,
            onefile=False,
            console=False,
            debug=[],
            python_options=[],
            strip=False,
            noupx=False,
            upx_exclude=[],
            runtime_tmpdir=None,
            contents_directory=None,
            pathex=[str(ROOT / "src")],
            version_file=None,
            specpath=str(spec_root),
            bootloader_ignore_signals=False,
            disable_windowed_traceback=False,
            datas=[
                (str(ROOT / "assets"), "assets"),
                (str(ROOT / "logo"), "logo"),
                (str(ROOT / "scripts" / "apply_update.ps1"), "scripts"),
            ],
            binaries=[],
            icon_file=[str(generated_icon)] if generated_icon is not None else None,
            manifest=None,
            resources=[],
            bundle_identifier=None,
            hiddenimports=[],
            hookspath=[],
            runtime_hooks=[],
            excludes=EXCLUDED_MODULES,
            uac_admin=False,
            uac_uiaccess=False,
            collect_submodules=[],
            collect_binaries=[],
            collect_data=[],
            collect_all=[],
            copy_metadata=[],
            splash=None,
            recursive_copy_metadata=[],
            target_arch=None,
            codesign_identity=None,
            entitlements_file=None,
            argv_emulation=False,
            hide_console=None,
            optimize=None,
            splash_center=None,
            shorthand_manifest=None,
        )
    )

    if sys.platform == "darwin":
        inject_macos_bundle_info_plist(spec_path)

    return spec_path


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

    spec_file = build_release_spec(spec_root=spec_root, generated_icon=generated_icon)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_file),
        "--noconfirm",
        "--clean",
        "--distpath",
        str(pyinstaller_dist),
        "--workpath",
        str(pyinstaller_work),
    ]
    subprocess.run(command, check=True)

    built_app_dir = pyinstaller_dist / built_output_name()
    release_root.mkdir(parents=True, exist_ok=False)
    # macOS .framework bundles rely on symlinks; dereferencing them greatly inflates the .app.
    shutil.copytree(built_app_dir, release_root / built_app_dir.name, symlinks=True)

    print(release_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
