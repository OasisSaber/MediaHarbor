from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MARKER_FILE = "AGENT_READ_ME_FIRST.md"
SKILL_FILE = "skill/untitled/SKILL.md"
TOOLS_JSON_REL = "download-tools/tools.json"
TOOLS_FILE = "tools.json"
SUPPORTED_SCHEMA_VERSION = 1
PREFERRED_PLATFORM = "windows-x64"
VALID_TOOL_KINDS = {"binary", "python-module"}
MODULE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


@dataclass
class ToolEntry:
    roles: list[str]
    required: bool = False
    platforms: dict[str, str] = field(default_factory=dict)
    kind: str = "binary"
    module: str | None = None

    @property
    def path(self) -> str:
        return self.platforms.get(PREFERRED_PLATFORM, "")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolEntry":
        platforms = data.get("platforms", {})
        if not platforms and data.get("path_windows"):
            platforms = {"windows-x64": data["path_windows"]}
        return cls(
            roles=data.get("roles", []),
            required=data.get("required", False),
            platforms=platforms,
            kind=data.get("kind", "binary"),
            module=data.get("module"),
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
    kind: str = "binary"
    module: str | None = None
    command: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    status: str
    tools: dict[str, ToolStatus] = field(default_factory=dict)


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
        f"Cannot find Untitled root: {MARKER_FILE}, {SKILL_FILE}, "
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
    if any(FORBIDDEN_CHARS.search(part) for part in parts):
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
    if not tools_raw:
        raise ValueError("No tools defined in registry")

    tools: dict[str, ToolEntry] = {}
    for name, entry_data in tools_raw.items():
        if not isinstance(entry_data, dict):
            raise ValueError(f"Tool entry for '{name}' must be a dictionary")
        entry = ToolEntry.from_dict(entry_data)
        if entry.kind not in VALID_TOOL_KINDS:
            raise ValueError(f"Tool '{name}' has unsupported kind '{entry.kind}'")
        if not isinstance(entry.roles, list):
            raise ValueError(f"Tool '{name}' roles must be a list")

        if entry.kind == "python-module":
            if not entry.module or not MODULE_NAME.fullmatch(entry.module):
                raise ValueError(f"Tool '{name}' requires a valid Python module name")
        else:
            for platform_key, path in entry.platforms.items():
                _validate_tool_path(path, f"{name}.{platform_key}")
            if entry.required and not entry.platforms:
                raise ValueError(f"Required binary tool '{name}' has no platform paths")
        tools[name] = entry
    return ToolRegistry(schema_version=schema_version, tools=tools)


def load_registry(start: Path | None = None) -> ToolRegistry:
    tools_path = get_paths(start)["tools_json"]
    if not tools_path.is_file():
        raise FileNotFoundError(f"Tools index not found: {tools_path}")
    data = json.loads(tools_path.read_text(encoding="utf-8"))
    return _validate_registry(data)


def resolve_registered_tool(
    name: str,
    registry: ToolRegistry | None = None,
    allow_system_path: bool = False,
) -> Path | None:
    """Resolve a binary tool to a controlled executable path.

    Python-module tools deliberately return None here. Call
    resolve_registered_command() when the caller can execute a command prefix.
    """
    if registry is None:
        try:
            registry = load_registry()
        except Exception:
            return None
    entry = registry.tools.get(name)
    if entry is None or entry.kind != "binary":
        return None

    raw = entry.path
    if raw:
        root = find_project_root()
        download_dir = root / "download-tools"
        candidate = download_dir / raw
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(download_dir.resolve())
        except (ValueError, OSError):
            return None
        if resolved.is_symlink():
            return None
        if resolved.is_file():
            return resolved

    if allow_system_path:
        system_path = shutil.which(name)
        if system_path:
            return Path(system_path)
    return None


resolve_tool = resolve_registered_tool


def resolve_registered_command(
    name: str,
    registry: ToolRegistry | None = None,
    allow_system_path: bool = False,
) -> list[str] | None:
    """Resolve a registered tool into a subprocess-safe argument prefix."""
    if registry is None:
        try:
            registry = load_registry()
        except Exception:
            return None
    entry = registry.tools.get(name)
    if entry is None:
        return None

    if entry.kind == "python-module":
        module = entry.module
        if module and importlib.util.find_spec(module) is not None:
            return [sys.executable, "-m", module]
        return None

    binary = resolve_registered_tool(
        name,
        registry=registry,
        allow_system_path=allow_system_path,
    )
    return [str(binary)] if binary else None


def check_tools(registry: ToolRegistry | None = None) -> CheckResult:
    if registry is None:
        registry = load_registry()
    result = CheckResult(status="READY")
    for name, entry in registry.tools.items():
        command = resolve_registered_command(name, registry=registry)
        exists = command is not None
        display_path = entry.path
        if entry.kind == "python-module":
            display_path = f"{sys.executable} -m {entry.module}"
        result.tools[name] = ToolStatus(
            name=name,
            path=display_path,
            exists=exists,
            roles=entry.roles,
            required=entry.required,
            kind=entry.kind,
            module=entry.module,
            command=command or [],
        )
        if entry.required and not exists:
            result.status = "DEGRADED"
    return result


def ensure_output_dir(start: Path | None = None) -> Path:
    output = get_paths(start)["output"]
    output.mkdir(parents=True, exist_ok=True)
    return output
