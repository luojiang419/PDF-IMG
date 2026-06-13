from __future__ import annotations

import re


INDEXED_NAME_PATTERN = re.compile(r"^(?P<index>\d{4})-(?P<label>.+)$")
VERSION_PATTERN = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


def next_index_name(existing_names: list[str], label: str) -> str:
    max_index = 0
    for name in existing_names:
        match = INDEXED_NAME_PATTERN.match(name)
        if match:
            max_index = max(max_index, int(match.group("index")))
    return f"{max_index + 1:04d}-{label}"


def parse_version(version_text: str) -> tuple[int, int, int]:
    cleaned = version_text[1:] if version_text.startswith("v") else version_text
    major, minor, patch = cleaned.split(".")
    return int(major), int(minor), int(patch)


def format_version(version: tuple[int, int, int]) -> str:
    return f"v{version[0]}.{version[1]}.{version[2]}"


def next_release_version(existing_names: list[str], minimum_version: str) -> str:
    minimum = parse_version(minimum_version)
    existing_versions = []
    for name in existing_names:
        match = VERSION_PATTERN.match(name)
        if match:
            existing_versions.append(
                (
                    int(match.group("major")),
                    int(match.group("minor")),
                    int(match.group("patch")),
                )
            )
    if not existing_versions:
        return format_version(minimum)
    highest = max(existing_versions)
    if highest < minimum:
        return format_version(minimum)
    return format_version((highest[0], highest[1], highest[2] + 1))
