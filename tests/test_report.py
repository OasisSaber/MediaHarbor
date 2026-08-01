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


def test_generate_coverage_report():
    from project import DownloadTask, Project, StoryNode
    from report import generate_coverage_report

    p = Project(
        name="cov-test",
        script="Sample text",
        story_nodes=[
            StoryNode(
                title="Scene 1", description="Desc", candidate_urls=["https://example.com/v1"]
            )
        ],
        tasks=[
            DownloadTask(url="https://example.com/v1", status="COMPLETED"),
            DownloadTask(url="https://example.com/v2", status="PENDING"),
        ],
    )
    from project import save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            save_project(p)
            report = generate_coverage_report("cov-test")
            assert report is not None
            assert "cov-test" in report
            assert "COMPLETED" in report
            assert "Pending" in report
        finally:
            os.chdir(cwd)


def test_save_report_and_handoff():
    from project import create_project, save_project
    from report import save_handoff, save_report

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("output-test")
            save_project(p)
            report_path = save_report("output-test")
            assert report_path is not None
            assert report_path.exists()
            handoff_path = save_handoff("output-test")
            assert handoff_path is not None
            assert handoff_path.exists()
        finally:
            os.chdir(cwd)


def test_coverage_report_groups_materials_by_editorial_status():
    from project import MaterialInfo, Project, save_project
    from report import generate_coverage_report

    p = Project(
        name="group-test",
        materials=[
            MaterialInfo(
                source_url="https://example.com/a",
                local_path="a.mp4",
                verified=True,
                technical_status="PASS",
                quality_status="UNKNOWN",
                editorial_status="UNREVIEWED",
            ),
            MaterialInfo(
                source_url="https://example.com/b",
                local_path="b.mp4",
                verified=True,
                technical_status="PASS",
                quality_status="WARN",
                editorial_status="REVIEW_REQUIRED",
                quality_reasons=["low-resolution"],
            ),
            MaterialInfo(
                source_url="https://example.com/c",
                local_path="c.mp4",
                verified=True,
                technical_status="PASS",
                quality_status="REJECT",
                editorial_status="REJECT",
                override_metadata={"human": "kept for archival"},
            ),
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            save_project(p)
            report = generate_coverage_report("group-test")
            assert report is not None
            assert "### unassessed" in report
            assert "### needs review" in report
            assert "### rejected" in report
            assert "technical: PASS" in report
            assert "quality: WARN" in report
            assert "low-resolution" in report
            assert "kept for archival" in report
            assert "?" not in report.split("## Materials")[1]
        finally:
            os.chdir(cwd)


def test_handoff_story_notes_show_nodes():
    from project import MaterialInfo, Project, StoryNode, save_project
    from report import generate_handoff

    p = Project(
        name="handoff-story-notes-test",
        script="原始脚本内容",
        story_nodes=[
            StoryNode(
                title="第3幕-点火升空",
                description="发射现场素材",
                candidate_urls=["https://example.com/a"],
            )
        ],
        materials=[
            MaterialInfo(
                source_url="https://example.com/a",
                local_path="a.mp4",
                verified=True,
            )
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            save_project(p)
            handoff = generate_handoff("handoff-story-notes-test")
            assert handoff is not None
            assert "### 第3幕-点火升空" in handoff
            assert "发射现场素材" in handoff
            assert "a.mp4" in handoff
            assert "https://example.com/a" in handoff
        finally:
            os.chdir(cwd)


def test_handoff_shows_assessment_states():
    from project import MaterialInfo, Project, save_project
    from report import generate_handoff

    p = Project(
        name="handoff-test",
        materials=[
            MaterialInfo(
                source_url="https://example.com/a",
                local_path="a.mp4",
                verified=True,
                technical_status="PASS",
                quality_status="UNKNOWN",
                editorial_status="UNREVIEWED",
            )
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            save_project(p)
            handoff = generate_handoff("handoff-test")
            assert handoff is not None
            assert "Technical: PASS" in handoff
            assert "Quality: UNKNOWN" in handoff
            assert "Editorial: UNREVIEWED" in handoff
        finally:
            os.chdir(cwd)
