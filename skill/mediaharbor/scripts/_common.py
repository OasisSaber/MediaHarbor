from __future__ import annotations

import json
import platform as _platform
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MARKER_FILE = "AGENT_READ_ME_FIRST.md"
SKILL_FILE = "skill/mediaharbor/SKILL.md"
TOOLS_JSON_REL = "download-tools/tools.json"
TOOLS_FILE = "tools.json"
SUPPORTED_SCHEMA_VERSION = 1


def detect_platform() -> str:
    system = _platform.system()
    machine = _platform.machine().lower()
    if system == "Windows":
        return "windows-x64"
    if system == "Linux":
        if machine in ("x86_64", "amd64"):
            return "linux-x64"
        raise RuntimeError(f"Unsupported CPU architecture for Linux: {machine}")
    if system == "Darwin":
        if machine in ("arm64", "aarch64"):
            return "macos-arm64"
        raise RuntimeError(f"Unsupported CPU architecture for macOS: {machine}")
    raise RuntimeError(f"Unsupported operating system: {system}")


@dataclass
class ToolEntry:
    roles: list[str]
    required: bool = False
    platforms: dict[str, str] = field(default_factory=dict)
    system_name: str | None = None

    @property
    def path(self) -> str:
        try:
            key = detect_platform()
            return self.platforms.get(key, "")
        except RuntimeError:
            return ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolEntry:
        platforms = data.get("platforms", {})
        if not platforms and data.get("path_windows"):
            platforms = {"windows-x64": data["path_windows"]}
        return cls(
            roles=data.get("roles", []),
            required=data.get("required", False),
            platforms=platforms,
            system_name=data.get("system_name"),
        )


@dataclass
class ToolRegistry:
    schema_version: int
    tools: dict[str, ToolEntry] = field(default_factory=dict)


@dataclass
class ToolStatus:
    name: str
    path: str
    exists: bool
    roles: list[str]
    required: bool
    source: str = ""


@dataclass
class CheckResult:
    status: str
    tools: dict[str, ToolStatus] = field(default_factory=dict)
    platform: str = ""


def find_project_root(start: Path | None = None) -> Path:
    if start is None:
        start = Path(__file__).resolve()
    else:
        start = start.resolve()

    for parent in [start] + list(start.parents):
        if (
            (parent / MARKER_FILE).is_file()
            and (parent / SKILL_FILE).is_file()
            and (parent / TOOLS_JSON_REL).is_file()
        ):
            return parent

    cwd = Path.cwd().resolve()
    if cwd != start:
        for parent in [cwd] + list(cwd.parents):
            if (
                (parent / MARKER_FILE).is_file()
                and (parent / SKILL_FILE).is_file()
                and (parent / TOOLS_JSON_REL).is_file()
            ):
                return parent

    raise RuntimeError(
        f"Cannot find MediaHarbor root: {MARKER_FILE}, {SKILL_FILE}, "
        f"{TOOLS_JSON_REL} not found from {start}"
    )


def get_paths(start: Path | None = None) -> dict[str, Path]:
    root = find_project_root(start)
    return {
        "root": root,
        "download_tools": root / "download-tools",
        "output": root / "output",
        "tools_json": root / "download-tools" / TOOLS_FILE,
    }


FORBIDDEN_CHARS = re.compile(r'[\x00-\x1f<>:"|?*]')


def _validate_tool_path(raw: str, tool_name: str) -> str:
    if not raw or not raw.strip():
        raise ValueError(f"Empty path for tool '{tool_name}'")
    norm = raw.replace("\\", "/")
    if norm.startswith("/") or (len(norm) >= 2 and norm[1] == ":"):
        raise ValueError(f"Absolute path not allowed for tool '{tool_name}': {raw}")
    if ".." in norm.split("/"):
        raise ValueError(f"Path traversal not allowed for tool '{tool_name}': {raw}")
    parts = norm.split("/")
    if any(FORBIDDEN_CHARS.search(p) for p in parts):
        raise ValueError(f"Illegal characters in path for tool '{tool_name}': {raw}")
    return norm


def _validate_registry(data: dict[str, Any]) -> ToolRegistry:
    schema_version = data.get("schema_version", 0)
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema version: {schema_version} (expected {SUPPORTED_SCHEMA_VERSION})"
        )
    tools_raw = data.get("tools")
    if not isinstance(tools_raw, dict):
        raise ValueError("'tools' must be a dictionary")
    tools: dict[str, ToolEntry] = {}
    seen_names: set[str] = set()
    for name, entry_data in tools_raw.items():
        if not isinstance(entry_data, dict):
            raise ValueError(f"Tool entry for '{name}' must be a dictionary")
        if name in seen_names:
            raise ValueError(f"Duplicate tool name: '{name}'")
        seen_names.add(name)
        entry = ToolEntry.from_dict(entry_data)
        for platform_key, path in entry.platforms.items():
            _validate_tool_path(path, f"{name}.{platform_key}")
        if entry.required and not entry.platforms:
            raise ValueError(f"Required tool '{name}' has no platform paths")
        tools[name] = entry
    if not tools:
        raise ValueError("No tools defined in registry")
    return ToolRegistry(schema_version=schema_version, tools=tools)


def load_registry(start: Path | None = None) -> ToolRegistry:
    paths = get_paths(start)
    tools_path = paths["tools_json"]
    if not tools_path.is_file():
        raise FileNotFoundError(f"Tools index not found: {tools_path}")
    data = json.loads(tools_path.read_text(encoding="utf-8"))
    return _validate_registry(data)


def resolve_registered_tool(
    name: str,
    registry: ToolRegistry | None = None,
    allow_system_path: bool = False,
) -> Path | None:
    if registry is None:
        try:
            registry = load_registry()
        except Exception:
            return None
    entry = registry.tools.get(name)
    if entry is None:
        return None
    raw = entry.path
    if not raw:
        return None
    root = find_project_root()
    dl_dir = root / "download-tools"
    candidate = dl_dir / raw
    try:
        resolved = candidate.resolve(strict=False)
        dl_resolved = dl_dir.resolve()
        resolved.relative_to(dl_resolved)
    except (ValueError, OSError):
        return None
    if resolved.is_symlink():
        return None
    if resolved.is_file():
        return resolved
    if allow_system_path:
        binary = getattr(entry, "system_name", None) or name
        sys_path = shutil.which(binary)
        if sys_path:
            return Path(sys_path)
    return None


resolve_tool = resolve_registered_tool


def check_tools(
    registry: ToolRegistry | None = None,
    allow_system_path: bool = False,
) -> CheckResult:
    platform_key = ""
    try:
        platform_key = detect_platform()
    except RuntimeError:
        pass
    if registry is None:
        try:
            registry = load_registry()
        except Exception:
            return CheckResult(status="ERROR", platform=platform_key)
    root = find_project_root()
    result = CheckResult(status="READY", platform=platform_key)
    for name, entry in registry.tools.items():
        raw = entry.path
        path_exists = False
        source = ""
        resolved_path = raw
        if raw:
            candidate = root / "download-tools" / raw
            path_exists = candidate.is_file()
            if path_exists:
                source = "registered"
        if not path_exists and allow_system_path:
            binary = getattr(entry, "system_name", None) or name
            sys_path = shutil.which(binary)
            if sys_path:
                path_exists = True
                source = "system_path"
                resolved_path = sys_path
        status = ToolStatus(
            name=name,
            path=resolved_path,
            exists=path_exists,
            roles=entry.roles,
            required=entry.required,
            source=source,
        )
        result.tools[name] = status
        if entry.required and not path_exists:
            result.status = "DEGRADED"
    return result


def ensure_output_dir(start: Path | None = None) -> Path:
    paths = get_paths(start)
    paths["output"].mkdir(parents=True, exist_ok=True)
    return paths["output"]
