from __future__ import annotations

import json
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
    tjson = (
        '{"schema_version": 1, "tools": {"d": {"roles": ["t"], '
        '"platforms": {"windows-x64": "d/d.exe"}}}}'
    )
    (root / "download-tools" / "tools.json").write_text(tjson)
    (root / "skill" / "mediaharbor").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "mediaharbor" / "SKILL.md").write_text(
        "---\ntitle: t\n---\n", encoding="utf-8"
    )


def test_sha256_consistent():
    from orchestrator import _sha256

    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "test.bin"
        f.write_bytes(b"hello world")
        h1 = _sha256(f)
        h2 = _sha256(f)
        assert h1 == h2
        assert len(h1) == 64


def test_validate_downloaded_file_missing():
    from orchestrator import _validate_downloaded_file

    result = _validate_downloaded_file(Path("/nonexistent/file.mp4"), Path("/tmp"))
    assert result.status == "VALIDATION_FAILED"


def test_generate_source_json_includes_sha256():
    from orchestrator import _generate_source_json, _sha256
    from process_runner import BackendResult
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("source-json-test")
            save_project(p)

            video = Path(tmp) / "output" / "source-json-test" / "assets" / "originals"
            video.mkdir(parents=True)
            test_file = video / "sample.mp4"
            test_file.write_bytes(b"fake media content for testing")

            be_result = BackendResult(
                status="SUCCESS",
                output_paths=[test_file],
                attempts=[],
            )
            result = _generate_source_json(
                "source-json-test",
                "https://example.com/v?token=abc&q=1",
                be_result,
                "yt-dlp",
                main_file=test_file,
            )
            assert result is not None
            data = json.loads(result.read_text(encoding="utf-8"))
            assert data["sha256"] == _sha256(test_file)
            assert data["sha256"] is not None
            assert "REDACTED" in data["display_url"]
        finally:
            os.chdir(cwd)


def test_generate_source_json_nonexistent_project():
    from orchestrator import _generate_source_json
    from process_runner import BackendResult

    result = _generate_source_json(
        "nonexistent-project",
        "https://example.com/v",
        BackendResult(status="SUCCESS", output_paths=[Path("/tmp/fake.mp4")]),
        "yt-dlp",
        main_file=Path("/tmp/fake.mp4"),
    )
    assert result is None


def test_process_pending_streamlink_success():
    from unittest.mock import patch

    from _common import ensure_output_dir
    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, AttemptInfo, BackendResult, ProcessResult
    from project import create_project, load_project, save_project
    from safe_path import resolve_project_dir

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("streamlink-success-test")
            save_project(p)

            root = ensure_output_dir()
            pdir = resolve_project_dir(root, "streamlink-success-test")
            asset_dir = pdir / "assets" / "originals"
            asset_dir.mkdir(parents=True, exist_ok=True)
            fake_file = asset_dir / "stream.ts"
            fake_file.write_text("dummy media content")

            add_candidate("streamlink-success-test", "https://example.com/live")

            with (
                patch("orchestrator.download_with_fallback") as mock_dl,
                patch("orchestrator._validate_downloaded_file") as mock_val,
            ):
                mock_dl.return_value = (
                    BackendResult(
                        status=SUCCESS,
                        output_paths=[fake_file],
                        stdout="",
                        stderr="",
                        attempts=[
                            AttemptInfo(1, "streamlink", SUCCESS, 0, 1.0, False, ""),
                        ],
                    ),
                    "streamlink",
                )
                mock_val.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )

                results = process_pending("streamlink-success-test")
                assert results["success"] == 1
                assert results["failed"] == 0

                proj = load_project("streamlink-success-test")
                assert len(proj.tasks) == 1
                assert proj.tasks[0].status == "COMPLETED"
                assert proj.tasks[0].backend == "streamlink"
                assert str(fake_file) in proj.tasks[0].output_paths
        finally:
            os.chdir(cwd)
