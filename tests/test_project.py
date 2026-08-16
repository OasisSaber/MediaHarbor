from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skill" / "bagitup" / "scripts"))


def _setup_temp_project(tmp: str):
    root = Path(tmp)
    (root / "AGENT_READ_ME_FIRST.md").write_text("")
    (root / "download-tools").mkdir(parents=True)
    tools_json = (
        '{"schema_version": 1, "tools": {"dummy": {"roles": ["test"], '
        '"platforms": {"windows-x64": "dummy/dummy.exe"}}}}'
    )
    (root / "download-tools" / "tools.json").write_text(tools_json)
    (root / "skill" / "bagitup").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "bagitup" / "SKILL.md").write_text(
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


def test_failed_primary_replace_preserves_last_valid_project():
    from unittest.mock import patch

    import project as project_module
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project = create_project("replace-failure", "version one")
            save_project(project)
            project.script = "version two"
            real_replace = project_module.os.replace
            replace_calls = 0

            def fail_second_replace(source, destination):
                nonlocal replace_calls
                replace_calls += 1
                if replace_calls == 2:
                    raise OSError("injected primary replace failure")
                return real_replace(source, destination)

            with patch("project.os.replace", side_effect=fail_second_replace):
                try:
                    save_project(project)
                except OSError:
                    pass

            loaded = load_project("replace-failure")
            assert loaded is not None
            assert loaded.script == "version one"
        finally:
            os.chdir(cwd)


def test_missing_primary_is_restored_from_backup():
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project = create_project("backup-recovery", "version one")
            path = save_project(project)
            project.script = "version two"
            save_project(project)
            path.unlink()

            loaded = load_project("backup-recovery")

            assert loaded is not None
            assert loaded.script == "version one"
            assert path.is_file()
        finally:
            os.chdir(cwd)


def test_corrupt_primary_is_restored_from_backup():
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project = create_project("corrupt-recovery", "version one")
            path = save_project(project)
            project.script = "version two"
            save_project(project)
            path.write_text("{corrupt", encoding="utf-8")

            loaded = load_project("corrupt-recovery")

            assert loaded is not None
            assert loaded.script == "version one"
            assert json.loads(path.read_text(encoding="utf-8"))["script"] == "version one"
        finally:
            os.chdir(cwd)


def test_legacy_material_migrates_to_conservative_assessment():
    from project import MaterialInfo, _migrate_material_assessment

    verified = MaterialInfo(source_url="u", local_path="p", verified=True)
    _migrate_material_assessment(verified)
    assert verified.technical_status == "PASS"
    assert verified.quality_status == "UNKNOWN"
    assert verified.editorial_status == "UNREVIEWED"

    unverified = MaterialInfo(source_url="u", local_path="p", verified=False)
    _migrate_material_assessment(unverified)
    assert unverified.technical_status == "UNKNOWN"

    explicit = MaterialInfo(
        source_url="u",
        local_path="p",
        verified=True,
        technical_status="FAIL",
        quality_status="WARN",
        editorial_status="REVIEW_REQUIRED",
    )
    _migrate_material_assessment(explicit)
    assert explicit.technical_status == "FAIL"
    assert explicit.quality_status == "WARN"
    assert explicit.editorial_status == "REVIEW_REQUIRED"


def test_saved_project_roundtrips_assessment_fields():
    import json

    from project import MaterialInfo, create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "AGENT_READ_ME_FIRST.md").write_text("")
        (root / "download-tools").mkdir(parents=True)
        (root / "download-tools" / "tools.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "tools": {"d": {"roles": ["t"], "platforms": {"windows-x64": "d/d.exe"}}},
                }
            )
        )
        (root / "skill" / "bagitup").mkdir(parents=True)
        (root / "skill" / "bagitup" / "SKILL.md").write_text("---\ntitle: test\n---\n")
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("assessment-roundtrip")
            p.materials.append(
                MaterialInfo(
                    source_url="u",
                    local_path="p",
                    verified=True,
                    technical_status="PASS",
                    quality_status="UNKNOWN",
                    editorial_status="UNREVIEWED",
                    assessment_timestamp="2026-01-01T00:00:00+00:00",
                )
            )
            save_project(p)
            loaded = load_project("assessment-roundtrip")
            material = loaded.materials[0]
            assert material.technical_status == "PASS"
            assert material.quality_status == "UNKNOWN"
            assert material.editorial_status == "UNREVIEWED"
        finally:
            os.chdir(cwd)
