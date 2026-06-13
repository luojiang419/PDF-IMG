from __future__ import annotations

import re
import sys
from pathlib import Path


WINDOWS_FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*]+')


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).joinpath(*parts)
    return project_root().joinpath(*parts)


def sanitize_name(value: str, fallback: str = "untitled") -> str:
    cleaned = WINDOWS_FORBIDDEN_CHARS.sub("_", value).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or fallback


def ensure_unique_output_dir(output_root: Path, preferred_name: str) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_name(preferred_name, fallback="pdf")
    candidate = output_root / safe_name
    index = 2
    while candidate.exists():
        candidate = output_root / f"{safe_name}_{index:02d}"
        index += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate
