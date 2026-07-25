from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skill" / "mediaharbor" / "scripts"))


def _setup_temp_project(tmp: str):
    root = Path(tmp)
    (root / "AGENT_READ_ME_FIRST.md").write_text("")
    (root / "download-tools").mkdir(parents=True)
    tools_json = (
        '{"schema_version": 1, "tools": {"dummy": {"roles": ["test"], '
        '"platforms": {"windows-x64": "dummy/dummy.exe"}}}}'
    )
    (root / "download-tools" / "tools.json").write_text(tools_json)
    (root / "skill" / "mediaharbor").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "mediaharbor" / "SKILL.md").write_text(
        "---\ntitle: test\n---\n", encoding="utf-8"
    )


def test_create_project():
    from project import create_project

    p = create_project("test-project", "sample script")
    assert p.name == "test-project"
    assert p.script == "sample script"
    assert p.schema_version == 1
    assert len(p.tasks) == 0
    assert len(p.story_nodes) == 0


def test_save_and_load_project():
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("save-test", "hello")
            path = save_project(p)
            assert path.exists()
            loaded = load_project("save-test")
            assert loaded is not None
            assert loaded.name == "save-test"
            assert loaded.script == "hello"
        finally:
            os.chdir(cwd)


def test_project_with_story_nodes():
    from project import StoryNode, create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("node-test")
            node = StoryNode(
                title="Opening Scene",
                description="City skyline at dusk",
                search_terms=["city skyline dusk", "aerial city"],
                candidate_urls=["https://example.com/vid1"],
            )
            p.story_nodes.append(node)
            save_project(p)
            loaded = load_project("node-test")
            assert loaded is not None
            assert len(loaded.story_nodes) == 1
            assert loaded.story_nodes[0].title == "Opening Scene"
        finally:
            os.chdir(cwd)


def test_save_keeps_backup_of_previous_version():
    from project import create_project, load_project, project_dir, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("bak-test", "v1")
            save_project(p)
            p.script = "v2"
            save_project(p)

            pdir = project_dir("bak-test")
            main = pdir / "project.json"
            bak = pdir / "project.json.bak"
            assert main.is_file()
            assert bak.is_file()
            assert load_project("bak-test").script == "v2"
            assert json.loads(bak.read_text(encoding="utf-8"))["script"] == "v1"
        finally:
            os.chdir(cwd)


def test_load_recovers_from_bak_when_main_missing():
    from project import create_project, load_project, project_dir, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("bak-recover", "first")
            save_project(p)
            p.script = "second"
            save_project(p)

            (project_dir("bak-recover") / "project.json").unlink()
            loaded = load_project("bak-recover")
            assert loaded is not None
            assert loaded.script == "first"
        finally:
            os.chdir(cwd)


def test_atomic_write_replace_failure_keeps_last_valid():
    import project as project_mod
    from project import create_project, load_project, project_dir, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("fail-replace", "v1")
            save_project(p)
            p.script = "v2"
            save_project(p)

            p.script = "v3"
            orig = project_mod.os.replace

            def flaky(src, dst):
                if dst.suffix == ".json":
                    raise OSError("simulated final replace failure")
                return orig(src, dst)

            with patch("project.os.replace", side_effect=flaky):
                with pytest.raises(OSError):
                    save_project(p)

            loaded = load_project("fail-replace")
            assert loaded is not None
            assert loaded.script == "v2"
            assert not (project_dir("fail-replace") / "project.json.tmp").exists()
        finally:
            os.chdir(cwd)


def test_recover_stale_running_resets_orphaned_tasks():
    from project import (
        DownloadTask,
        create_project,
        load_project,
        recover_stale_running,
        save_project,
    )

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("recover-test", "script")
            p.tasks.append(DownloadTask(url="https://example.com/a", status="RUNNING"))
            p.tasks.append(DownloadTask(url="https://example.com/b", status="PENDING"))
            save_project(p)

            count = recover_stale_running("recover-test")
            assert count == 1
            loaded = load_project("recover-test")
            assert loaded.tasks[0].status == "PENDING"
            assert loaded.tasks[0].started_at is None
            assert loaded.tasks[1].status == "PENDING"
        finally:
            os.chdir(cwd)
