from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "bagitup" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_e2e_source_workspace_with_license_and_workflow():
    # E2E over the source workspace directly (no release assembly).
    old_cwd = os.getcwd()
    project_name = f"e2e-{uuid.uuid4().hex[:8]}"
    try:
        os.chdir(str(REPO_ROOT))

        from _common import ensure_output_dir
        from acquisition import add_candidate, complete_task, start_task
        from orchestrator import _generate_source_json, _sha256
        from process_runner import BackendResult
        from project import create_project, load_project, save_project
        from report import generate_coverage_report, generate_handoff
        from safe_path import resolve_project_dir

        # 1) Create project and add candidate
        p = create_project(project_name, script="E2E source workspace test")
        save_project(p)
        add_candidate(project_name, "https://example.com/video?id=1")

        # 2) Simulate download: create fake output file + compute hash
        root = ensure_output_dir()
        pdir = resolve_project_dir(root, project_name)
        asset_dir = pdir / "assets" / "originals"
        asset_dir.mkdir(parents=True, exist_ok=True)
        fake_file = asset_dir / "fake-sample.mp4"
        fake_file.write_bytes(b"fake media content for E2E testing")
        file_hash = _sha256(fake_file)
        assert len(file_hash) == 64

        # 3) Generate source.json with BackendResult contract
        be_result = BackendResult(
            status="SUCCESS",
            output_paths=[fake_file],
            attempts=[],
        )
        src_path = _generate_source_json(
            project_name,
            "https://example.com/video?id=1",
            be_result,
            "yt-dlp",
            main_file=fake_file,
        )
        assert src_path is not None
        src_data = json.loads(src_path.read_text(encoding="utf-8"))
        assert src_data["sha256"] == file_hash

        # 4) Complete task with full MaterialInfo
        started = start_task(project_name, "https://example.com/video?id=1")
        assert started is not None
        assert started.status == "RUNNING"

        completed = complete_task(
            project_name,
            "https://example.com/video?id=1",
            "yt-dlp",
            [str(fake_file)],
            file_hash=file_hash,
            format="mp4",
            duration=30.0,
            width=1920,
            height=1080,
        )
        assert completed is not None
        assert completed.status == "COMPLETED"

        # 5) Verify MaterialInfo is complete
        proj = load_project(project_name)
        assert len(proj.materials) == 1
        m = proj.materials[0]
        assert m.verified is True
        assert m.file_hash == file_hash
        assert m.source_url == "https://example.com/video?id=1"
        assert m.format == "mp4"
        assert m.duration == 30.0
        assert m.width == 1920
        assert m.height == 1080

        # 6) Reports
        report = generate_coverage_report(project_name)
        assert report is not None
        assert "1" in report

        handoff = generate_handoff(project_name)
        assert handoff is not None
        assert "Materials Collected" in handoff
    finally:
        os.chdir(old_cwd)
        project_dir = REPO_ROOT / "output" / project_name
        if project_dir.is_dir():
            shutil.rmtree(project_dir, ignore_errors=True)
