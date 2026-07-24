from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_release_layout():
    assert (REPO_ROOT / "AGENT_READ_ME_FIRST.md").is_file()
    assert (REPO_ROOT / "skill" / "mediaharbor" / "SKILL.md").is_file()
    assert (REPO_ROOT / "skill" / "mediaharbor" / "scripts").is_dir()
    assert (REPO_ROOT / "download-tools" / "tools.json").is_file()


def test_skill_scripts_run_in_release_simulation():
    with tempfile.TemporaryDirectory() as tmp:
        release_root = Path(tmp) / "MediaHarbor"
        release_root.mkdir()

        for sub in ["skill/mediaharbor/scripts", "skill/mediaharbor/references", "download-tools"]:
            (release_root / sub).mkdir(parents=True)

        shutil.copy2(REPO_ROOT / "AGENT_READ_ME_FIRST.md", release_root / "AGENT_READ_ME_FIRST.md")
        shutil.copy2(
            REPO_ROOT / "skill" / "mediaharbor" / "SKILL.md",
            release_root / "skill" / "mediaharbor" / "SKILL.md",
        )
        shutil.copy2(
            REPO_ROOT / "download-tools" / "tools.json",
            release_root / "download-tools" / "tools.json",
        )
        for script in ["_common.py", "locate_root.py", "check_tools.py"]:
            shutil.copy2(
                REPO_ROOT / "skill" / "mediaharbor" / "scripts" / script,
                release_root / "skill" / "mediaharbor" / "scripts" / script,
            )

        env = os.environ.copy()
        env["PYTHONPATH"] = str(release_root / "skill" / "mediaharbor" / "scripts")

        result = subprocess.run(
            [
                sys.executable,
                str(release_root / "skill" / "mediaharbor" / "scripts" / "locate_root.py"),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "root" in result.stdout

        result = subprocess.run(
            [
                sys.executable,
                str(release_root / "skill" / "mediaharbor" / "scripts" / "check_tools.py"),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=env,
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
        cwd=str(REPO_ROOT / "skill" / "mediaharbor" / "scripts"),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
