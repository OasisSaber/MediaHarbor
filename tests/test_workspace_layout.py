from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_source_workspace_layout():
    assert (REPO_ROOT / "AGENT_READ_ME_FIRST.md").is_file()
    assert (REPO_ROOT / "skill" / "bagitup" / "SKILL.md").is_file()
    assert (REPO_ROOT / "skill" / "bagitup" / "scripts").is_dir()
    assert (REPO_ROOT / "download-tools" / "tools.json").is_file()
    assert (REPO_ROOT / "download-tools" / "routing.json").is_file()
    assert (REPO_ROOT / "download-tools" / "THIRD_PARTY_NOTICES.md").is_file()


def test_skill_scripts_run_in_source_workspace():
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "skill" / "bagitup" / "scripts" / "locate_root.py"),
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "root" in result.stdout

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "skill" / "bagitup" / "scripts" / "check_tools.py"),
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_scripts_do_not_require_pip_install():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from _common import find_project_root, get_paths, load_registry, check_tools",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT / "skill" / "bagitup" / "scripts"),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
