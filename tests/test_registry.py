from __future__ import annotations

import json
import platform
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from _common import SUPPORTED_SCHEMA_VERSION, ToolRegistry, detect_platform, load_registry


def test_detect_platform_returns_string():
    key = detect_platform()
    assert key in ("windows-x64", "linux-x64", "macos-arm64")


def test_detect_platform_matches_current_system():
    key = detect_platform()
    system = platform.system()
    if system == "Windows":
        assert key == "windows-x64"
    elif system == "Linux":
        assert key == "linux-x64"
    elif system == "Darwin":
        assert key == "macos-arm64"


def test_detect_platform_windows_x64():
    with (
        mock.patch("platform.system", return_value="Windows"),
        mock.patch("platform.machine", return_value="AMD64"),
    ):
        assert detect_platform() == "windows-x64"


def test_detect_platform_linux_x64():
    with (
        mock.patch("platform.system", return_value="Linux"),
        mock.patch("platform.machine", return_value="x86_64"),
    ):
        assert detect_platform() == "linux-x64"


def test_detect_platform_linux_x64_alternate_name():
    with (
        mock.patch("platform.system", return_value="Linux"),
        mock.patch("platform.machine", return_value="amd64"),
    ):
        assert detect_platform() == "linux-x64"


def test_detect_platform_macos_arm64():
    with (
        mock.patch("platform.system", return_value="Darwin"),
        mock.patch("platform.machine", return_value="arm64"),
    ):
        assert detect_platform() == "macos-arm64"


def test_detect_platform_macos_arm64_alternate_name():
    with (
        mock.patch("platform.system", return_value="Darwin"),
        mock.patch("platform.machine", return_value="aarch64"),
    ):
        assert detect_platform() == "macos-arm64"


def test_detect_platform_unsupported_os_raises():
    with (
        mock.patch("platform.system", return_value="FreeBSD"),
        mock.patch("platform.machine", return_value="amd64"),
    ):
        with pytest.raises(RuntimeError, match="Unsupported operating system"):
            detect_platform()


def test_detect_platform_unsupported_linux_arch_raises():
    with (
        mock.patch("platform.system", return_value="Linux"),
        mock.patch("platform.machine", return_value="armv7l"),
    ):
        with pytest.raises(RuntimeError, match="Unsupported CPU architecture"):
            detect_platform()


def test_detect_platform_unsupported_macos_arch_raises():
    with (
        mock.patch("platform.system", return_value="Darwin"),
        mock.patch("platform.machine", return_value="x86_64"),
    ):
        with pytest.raises(RuntimeError, match="Unsupported CPU architecture"):
            detect_platform()


def test_toolentry_path_uses_dynamic_platform():
    from _common import ToolEntry

    entry = ToolEntry(
        roles=["test"],
        platforms={
            "windows-x64": "tool/win.exe",
            "linux-x64": "tool/linux",
            "macos-arm64": "tool/mac",
        },
    )
    key = detect_platform()
    assert entry.path == entry.platforms[key]


def test_toolentry_path_empty_when_platform_missing():
    from _common import ToolEntry

    entry = ToolEntry(
        roles=["test"],
        platforms={"windows-x64": "tool/win.exe"},
    )
    with (
        mock.patch("platform.system", return_value="Linux"),
        mock.patch("platform.machine", return_value="x86_64"),
    ):
        # linux-x64 not registered for this tool -> empty path, not an exception
        assert entry.path == ""


def test_toolentry_path_empty_when_platform_unsupported():
    from _common import ToolEntry

    entry = ToolEntry(
        roles=["test"],
        platforms={"windows-x64": "tool/win.exe"},
    )
    with (
        mock.patch("platform.system", return_value="FreeBSD"),
        mock.patch("platform.machine", return_value="amd64"),
    ):
        assert entry.path == ""


def _setup_tmp(root: Path):
    (root / "AGENT_READ_ME_FIRST.md").write_text("")
    (root / "skill" / "mediaharbor").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "mediaharbor" / "SKILL.md").write_text(
        "---\ntitle: test\n---\n", encoding="utf-8"
    )
    (root / "download-tools").mkdir(parents=True, exist_ok=True)


@pytest.fixture
def registry():
    return ToolRegistry(
        schema_version=SUPPORTED_SCHEMA_VERSION,
        tools={
            "test-tool": type(
                "ToolEntry",
                (),
                {
                    "platforms": {"windows-x64": "test/test.exe"},
                    "roles": ["test"],
                    "required": True,
                },
            )(),
        },
    )


def test_valid_registry_from_dict():
    data = {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "tools": {
            "yt-dlp": {
                "platforms": {"windows-x64": "yt-dlp/yt-dlp.exe"},
                "roles": ["probe"],
                "required": True,
            },
        },
    }
    from _common import ToolEntry

    tools = {name: ToolEntry.from_dict(entry) for name, entry in data["tools"].items()}
    assert "yt-dlp" in tools
    assert tools["yt-dlp"].platforms["windows-x64"] == "yt-dlp/yt-dlp.exe"


def test_backward_compat_path_windows():
    data = {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "tools": {
            "legacy": {
                "path_windows": "legacy/legacy.exe",
                "roles": ["test"],
                "required": False,
            },
        },
    }
    from _common import ToolEntry

    entry = ToolEntry.from_dict(data["tools"]["legacy"])
    assert entry.platforms["windows-x64"] == "legacy/legacy.exe"


def test_rejects_unsupported_schema():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_tmp(root)
        (root / "download-tools" / "tools.json").write_text(
            json.dumps(
                {
                    "schema_version": 999,
                    "tools": {"t": {"roles": ["x"], "platforms": {"windows-x64": "t.exe"}}},
                }
            )
        )
        with pytest.raises(ValueError, match="Unsupported schema"):
            load_registry(start=root)


def test_rejects_empty_tools():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_tmp(root)
        (root / "download-tools" / "tools.json").write_text(
            json.dumps({"schema_version": SUPPORTED_SCHEMA_VERSION, "tools": {}})
        )
        with pytest.raises(ValueError, match="No tools defined"):
            load_registry(start=root)


def test_rejects_null_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_tmp(root)
        (root / "download-tools" / "tools.json").write_text(
            json.dumps(
                {
                    "schema_version": SUPPORTED_SCHEMA_VERSION,
                    "tools": {
                        "bad": {
                            "platforms": {"windows-x64": ""},
                            "roles": ["test"],
                            "required": False,
                        },
                    },
                }
            )
        )
        with pytest.raises(ValueError, match="Empty path"):
            load_registry(start=root)


def test_rejects_traversal_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_tmp(root)
        (root / "download-tools" / "tools.json").write_text(
            json.dumps(
                {
                    "schema_version": SUPPORTED_SCHEMA_VERSION,
                    "tools": {
                        "bad": {
                            "platforms": {"windows-x64": "../escape.exe"},
                            "roles": ["test"],
                            "required": False,
                        },
                    },
                }
            )
        )
        with pytest.raises(ValueError, match="Path traversal"):
            load_registry(start=root)


def test_returns_empty_registry():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_tmp(root)
        (root / "download-tools" / "tools.json").write_text(
            json.dumps(
                {
                    "schema_version": SUPPORTED_SCHEMA_VERSION,
                    "tools": {
                        "opt": {
                            "platforms": {"windows-x64": "opt/opt.exe"},
                            "roles": ["test"],
                            "required": False,
                        },
                    },
                }
            )
        )
        registry = load_registry(start=root)
        assert len(registry.tools) == 1
