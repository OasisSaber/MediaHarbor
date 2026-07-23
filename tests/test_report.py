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
