from __future__ import annotations

from pathlib import Path


PREVIEW_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def list_preview_images(output_dir: Path | None) -> list[Path]:
    if output_dir is None or not output_dir.exists() or not output_dir.is_dir():
        return []

    preview_images: list[Path] = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name.lower()):
        if path.is_file() and path.suffix.lower() in PREVIEW_IMAGE_EXTENSIONS:
            preview_images.append(path)
    return preview_images


def find_preview_image(output_dir: Path | None) -> Path | None:
    preview_images = list_preview_images(output_dir)
    return preview_images[0] if preview_images else None
