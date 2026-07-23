from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _setup_tmp(root: Path):
    (root / "AGENT_READ_ME_FIRST.md").write_text("")
    (root / "skill" / "mediaharbor").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "mediaharbor" / "SKILL.md").write_text(
        "---\ntitle: test\n---\n", encoding="utf-8"
    )
    (root / "download-tools").mkdir(parents=True, exist_ok=True)


def test_locate_root_from_script_dir():
    result = subprocess.run(
        [sys.executable, "locate_root.py", "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT / "skill" / "mediaharbor" / "scripts"),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    import json

    data = json.loads(result.stdout)
    assert data["root"] is not None
    assert "error" not in data or data["error"] is None


def test_locate_root_independent_of_cwd():
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "skill" / "mediaharbor" / "scripts" / "locate_root.py"),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=tmp,
        )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    import json

    data = json.loads(result.stdout)
    assert data["root"] is not None


def test_locate_root_with_spaces_in_path():
    with tempfile.TemporaryDirectory() as tmp:
        spaced_dir = Path(tmp) / "Media Harbor Test"
        spaced_dir.mkdir()
        _setup_tmp(spaced_dir)
        dummy_json = (
            '{"schema_version": 1, '
            '"tools": {"dummy": {"roles": ["test"], '
            '"platforms": {"windows-x64": "dummy/dummy.exe"}}}}'
        )
        (spaced_dir / "download-tools" / "tools.json").write_text(dummy_json)

        src_scripts = REPO_ROOT / "skill" / "mediaharbor" / "scripts"
        scripts_dir = spaced_dir / "skill" / "mediaharbor" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for fname in ["_common.py", "locate_root.py"]:
            (scripts_dir / fname).write_text(
                (src_scripts / fname).read_text(encoding="utf-8"), encoding="utf-8"
            )

        result = subprocess.run(
            [sys.executable, str(scripts_dir / "locate_root.py"), "--json"],
            capture_output=True,
            text=True,
            cwd=tmp,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        import json

        data = json.loads(result.stdout)
        assert data["root"] is not None


def test_rejects_false_root():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "AGENT_READ_ME_FIRST.md").write_text("")
        src = REPO_ROOT / "skill" / "mediaharbor" / "scripts"
        scripts_dir = root / "skill" / "mediaharbor" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "_common.py").write_text(
            (src / "_common.py").read_text(encoding="utf-8"), encoding="utf-8"
        )
        (scripts_dir / "locate_root.py").write_text(
            (src / "locate_root.py").read_text(encoding="utf-8"), encoding="utf-8"
        )
        result = subprocess.run(
            [sys.executable, str(scripts_dir / "locate_root.py"), "--json"],
            capture_output=True,
            text=True,
            cwd=tmp,
        )
        assert result.returncode != 0
