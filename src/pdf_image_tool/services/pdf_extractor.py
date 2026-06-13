from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf

from pdf_image_tool.core.models import PdfTaskResult
from pdf_image_tool.core.paths import ensure_unique_output_dir


LogCallback = Callable[[str], None] | None
NATIVE_EXTENSIONS = {"jpg", "jpeg", "png", "bmp", "tif", "tiff", "webp"}


def normalize_extension(extension: str) -> str:
    normalized = extension.lower().strip(".")
    aliases = {
        "jpe": "jpeg",
        "jfif": "jpeg",
    }
    return aliases.get(normalized, normalized)


def append_log(result: PdfTaskResult, message: str, callback: LogCallback) -> None:
    result.log_lines.append(message)
    if callback:
        callback(message)


def save_native_bytes(data: bytes, target_path: Path) -> None:
    target_path.write_bytes(data)


def save_pixmap_as_png(pixmap: pymupdf.Pixmap, target_path: Path) -> None:
    current = pixmap
    converted = None
    try:
        if current.colorspace is not None and current.colorspace.n > 3 and not current.alpha:
            converted = pymupdf.Pixmap(pymupdf.csRGB, current)
            current = converted
        current.save(target_path.as_posix())
    finally:
        if converted is not None:
            converted = None


def save_with_smask(document: pymupdf.Document, xref: int, smask: int, target_path: Path) -> None:
    base_image = document.extract_image(xref)
    mask_image = document.extract_image(smask)
    if not base_image or not mask_image:
        save_as_png(document, xref, target_path)
        return

    base_pixmap = pymupdf.Pixmap(base_image["image"])
    mask_pixmap = pymupdf.Pixmap(mask_image["image"])
    merged_pixmap = None
    rgb_pixmap = None
    try:
        merged_pixmap = pymupdf.Pixmap(base_pixmap, mask_pixmap)
        current = merged_pixmap
        if current.colorspace is not None and current.colorspace.n > 3 and not current.alpha:
            rgb_pixmap = pymupdf.Pixmap(pymupdf.csRGB, current)
            current = rgb_pixmap
        current.save(target_path.as_posix())
    except Exception:
        save_as_png(document, xref, target_path)
    finally:
        rgb_pixmap = None
        merged_pixmap = None
        mask_pixmap = None
        base_pixmap = None


def save_as_png(document: pymupdf.Document, xref: int, target_path: Path) -> None:
    pixmap = pymupdf.Pixmap(document, xref)
    try:
        save_pixmap_as_png(pixmap, target_path)
    finally:
        pixmap = None


def extract_images_from_pdf(pdf_path: Path, output_root: Path, log_callback: LogCallback = None) -> PdfTaskResult:
    result = PdfTaskResult(pdf_path=pdf_path)

    try:
        document = pymupdf.open(pdf_path.as_posix())
    except Exception as exc:
        result.status = "failed"
        result.error_message = f"无法打开 PDF：{exc}"
        append_log(result, result.error_message, log_callback)
        return result

    try:
        if document.needs_pass:
            result.status = "failed"
            result.error_message = "PDF 已加密，当前版本暂不支持输入密码。"
            append_log(result, result.error_message, log_callback)
            return result

        result.page_count = document.page_count
        result.output_dir = ensure_unique_output_dir(output_root, pdf_path.stem)
        append_log(result, f"输出目录：{result.output_dir}", log_callback)

        for page_number in range(document.page_count):
            page = document.load_page(page_number)
            image_refs = page.get_images(full=True)
            mask_xrefs = {item[1] for item in image_refs if len(item) > 1 and item[1] > 0}
            exported_index = 0

            for image_ref in image_refs:
                xref = image_ref[0]
                smask = image_ref[1] if len(image_ref) > 1 else 0

                if xref in mask_xrefs:
                    result.skipped_count += 1
                    append_log(
                        result,
                        f"第 {page_number + 1} 页跳过遮罩对象 xref={xref}",
                        log_callback,
                    )
                    continue

                image_data = document.extract_image(xref)
                if not image_data or not image_data.get("image"):
                    result.skipped_count += 1
                    append_log(
                        result,
                        f"第 {page_number + 1} 页跳过不可导出的图片对象 xref={xref}",
                        log_callback,
                    )
                    continue

                exported_index += 1
                file_stem = f"page-{page_number + 1:03d}_img-{exported_index:03d}"
                extension = normalize_extension(image_data.get("ext", "png"))

                if smask > 0:
                    target_path = result.output_dir / f"{file_stem}.png"
                    save_with_smask(document, xref, smask, target_path)
                    result.converted_count += 1
                    result.extracted_count += 1
                    append_log(
                        result,
                        f"第 {page_number + 1} 页图片 {exported_index} 已合成透明通道并导出为 PNG",
                        log_callback,
                    )
                    continue

                if extension in NATIVE_EXTENSIONS:
                    target_path = result.output_dir / f"{file_stem}.{extension}"
                    save_native_bytes(image_data["image"], target_path)
                    result.extracted_count += 1
                    append_log(
                        result,
                        f"第 {page_number + 1} 页图片 {exported_index} 原样导出为 {extension.upper()}",
                        log_callback,
                    )
                    continue

                target_path = result.output_dir / f"{file_stem}.png"
                save_as_png(document, xref, target_path)
                result.converted_count += 1
                result.extracted_count += 1
                append_log(
                    result,
                    f"第 {page_number + 1} 页图片 {exported_index} 从 {extension.upper()} 转为 PNG",
                    log_callback,
                )

        if result.extracted_count == 0:
            result.status = "no_images"
            append_log(result, "该 PDF 中未发现可导出的内嵌图片。", log_callback)
        else:
            result.status = "success" if result.error_message is None else "partial"
            append_log(
                result,
                f"完成：共导出 {result.extracted_count} 张图片，转换 {result.converted_count} 张，跳过 {result.skipped_count} 项。",
                log_callback,
            )
        return result
    except Exception as exc:
        result.status = "failed"
        result.error_message = f"提取失败：{exc}"
        append_log(result, result.error_message, log_callback)
        return result
    finally:
        document.close()
