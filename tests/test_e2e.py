from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "mediaharbor" / "scripts"


def test_e2e_isolated_release_with_license_and_workflow():
    sys.path.insert(0, str(SCRIPTS_DIR))

    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        try:
            # 1) Assemble release
            import subprocess

            r = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "assemble_release.py"),
                    "--output-dir",
                    str(tmp_root / "out"),
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            assert r.returncode == 0, f"assemble stderr: {r.stderr}"

            release_dir = tmp_root / "out" / "MediaHarbor"
            assert (release_dir / "LICENSE").is_file(), "LICENSE must be in release"
            marker_path = release_dir / "download-tools" / ".mediaharbor-release"
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            assert marker.get("package_type") == "shell"

            # 2) Switch to release dir (simulates running from outside source repo)
            rscripts = str(release_dir / "skill" / "mediaharbor" / "scripts")
            if rscripts not in sys.path:
                sys.path.insert(0, rscripts)

            os.chdir(str(release_dir))

            from _common import ensure_output_dir
            from acquisition import add_candidate, complete_task, start_task
            from orchestrator import _generate_source_json, _sha256
            from project import create_project, load_project, save_project
            from report import generate_coverage_report, generate_handoff
            from safe_path import resolve_project_dir

            # 3) Create project and add candidate
            p = create_project("e2e-release-test", script="E2E release test")
            save_project(p)
            add_candidate("e2e-release-test", "https://example.com/video?id=1")

            # 4) Simulate download: create fake output file + compute hash
            root = ensure_output_dir()
            pdir = resolve_project_dir(root, "e2e-release-test")
            asset_dir = pdir / "assets" / "originals"
            asset_dir.mkdir(parents=True, exist_ok=True)
            fake_file = asset_dir / "fake-sample.mp4"
            fake_file.write_bytes(b"fake media content for E2E testing")
            file_hash = _sha256(fake_file)
            assert len(file_hash) == 64

            # 5) Generate source.json
            src_path = _generate_source_json(
                "e2e-release-test",
                "https://example.com/video?id=1",
                fake_file,
                "yt-dlp",
                [],
            )
            assert src_path is not None
            src_data = json.loads(src_path.read_text(encoding="utf-8"))
            assert src_data["sha256"] == file_hash

            # 6) Complete task with full MaterialInfo
            started = start_task("e2e-release-test", "https://example.com/video?id=1")
            assert started is not None
            assert started.status == "RUNNING"

            completed = complete_task(
                "e2e-release-test",
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

            # 7) Verify MaterialInfo is complete
            proj = load_project("e2e-release-test")
            assert len(proj.materials) == 1
            m = proj.materials[0]
            assert m.verified is True
            assert m.file_hash == file_hash
            assert m.source_url == "https://example.com/video?id=1"
            assert m.format == "mp4"
            assert m.duration == 30.0
            assert m.width == 1920
            assert m.height == 1080

            # 8) Reports
            report = generate_coverage_report("e2e-release-test")
            assert report is not None
            assert "1" in report

            handoff = generate_handoff("e2e-release-test")
            assert handoff is not None
            assert "Materials Collected" in handoff

        finally:
            os.chdir(old_cwd)
