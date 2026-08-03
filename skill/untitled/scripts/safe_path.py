from __future__ import annotations

import re
from pathlib import Path

FORBIDDEN_CHARS = re.compile(r'[\x00-\x1f<>:"|?*]')
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}
MAX_NAME_LENGTH = 128


def validate_project_name(name: str) -> str:
    if not name or not name.strip():
        raise ValueError("Empty project name")
    name = name.strip()
    if "/" in name or "\\" in name:
        raise ValueError(f"Path separators not allowed in project name: {name}")
    if name in (".", ".."):
        raise ValueError(f"Reserved name not allowed: {name}")
    if ".." in name:
        raise ValueError(f"Path traversal not allowed in project name: {name}")
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Project name too long: {len(name)} > {MAX_NAME_LENGTH}")
    if FORBIDDEN_CHARS.search(name):
        raise ValueError(f"Illegal characters in project name: {name}")
    if name.rstrip().endswith(".") or name.rstrip().endswith(" "):
        raise ValueError(f"Trailing dot or space not allowed in project name: {name}")
    upper = name.upper().split(".")[0]
    if upper in RESERVED_NAMES:
        raise ValueError(f"Reserved name not allowed: {name}")
    return name


def resolve_project_dir(root: Path, name: str) -> Path:
    cleaned = validate_project_name(name)
    resolved = (root / cleaned).resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise ValueError(f"Path escapes output directory: {name}")
    return resolved
