from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _setup_temp_root(dst: Path):
    (dst / "AGENT_READ_ME_FIRST.md").write_text("")
    (dst / "download-tools").mkdir(parents=True, exist_ok=True)
    (dst / "skill" / "mediaharbor").mkdir(parents=True, exist_ok=True)
    (dst / "skill" / "mediaharbor" / "SKILL.md").write_text(
        "---\ntitle: test\n---\n", encoding="utf-8"
    )
    scripts_dir = dst / "skill" / "mediaharbor" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    src = REPO_ROOT / "skill" / "mediaharbor" / "scripts"
    for fname in ["_common.py", "check_tools.py"]:
        (scripts_dir / fname).write_text(
            (src / fname).read_text(encoding="utf-8"), encoding="utf-8"
        )


def test_check_tools_json_output():
    result = subprocess.run(
        [sys.executable, "check_tools.py", "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT / "skill" / "mediaharbor" / "scripts"),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert "status" in data
    assert data["status"] in ("READY", "DEGRADED", "ERROR")
    assert "tools" in data


def test_missing_required_tools_returns_degraded():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_temp_root(root)
        (root / "download-tools" / "tools.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "tools": {
                        "missing-req": {
                            "platforms": {"windows-x64": "nonexistent/nope.exe"},
                            "roles": ["test"],
                            "required": True,
                        },
                    },
                }
            )
        )

        result = subprocess.run(
            [
                sys.executable,
                str(root / "skill" / "mediaharbor" / "scripts" / "check_tools.py"),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=root,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["status"] == "DEGRADED"


def test_missing_optional_tools_do_not_cause_error():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_temp_root(root)
        (root / "download-tools" / "tools.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "tools": {
                        "missing-opt": {
                            "platforms": {"windows-x64": "nonexistent/opt.exe"},
                            "roles": ["test"],
                            "required": False,
                        },
                    },
                }
            )
        )

        result = subprocess.run(
            [
                sys.executable,
                str(root / "skill" / "mediaharbor" / "scripts" / "check_tools.py"),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=root,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["status"] == "READY"


def test_fake_executable_is_recognized():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_temp_root(root)
        tool_dir = root / "download-tools" / "my-tool"
        tool_dir.mkdir(parents=True)
        fake_exe = tool_dir / "my-tool.exe"
        fake_exe.write_text("fake-binary-content")

        (root / "download-tools" / "tools.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "tools": {
                        "my-tool": {
                            "platforms": {"windows-x64": "my-tool/my-tool.exe"},
                            "roles": ["test"],
                            "required": True,
                        },
                    },
                }
            )
        )

        result = subprocess.run(
            [
                sys.executable,
                str(root / "skill" / "mediaharbor" / "scripts" / "check_tools.py"),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=root,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["status"] == "READY"
        assert data["tools"]["my-tool"]["exists"] is True


def test_output_dir_created_on_demand():
    with tempfile.TemporaryDirectory() as tmp:
        rt = Path(tmp)
        _setup_temp_root(rt)
        (rt / "download-tools" / "tools.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "tools": {
                        "dummy": {
                            "roles": ["test"],
                            "platforms": {"windows-x64": "dummy/dummy.exe"},
                        }
                    },
                }
            )
        )

        script_path = rt / "skill" / "mediaharbor" / "scripts" / "check_tools.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "--json"],
            capture_output=True,
            text=True,
            cwd=tmp,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"


def test_json_output_is_parseable():
    result = subprocess.run(
        [sys.executable, "locate_root.py", "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT / "skill" / "mediaharbor" / "scripts"),
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, dict)

    result = subprocess.run(
        [sys.executable, "check_tools.py", "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT / "skill" / "mediaharbor" / "scripts"),
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, dict)
