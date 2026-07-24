from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

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
