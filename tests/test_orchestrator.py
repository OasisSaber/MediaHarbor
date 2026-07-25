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


def test_process_pending_download_exception_fails_task_and_continues():
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
            p = create_project("dl-exc-test")
            save_project(p)

            root = ensure_output_dir()
            pdir = resolve_project_dir(root, "dl-exc-test")
            asset_dir = pdir / "assets" / "originals"
            asset_dir.mkdir(parents=True, exist_ok=True)
            fake_b = asset_dir / "b.ts"
            fake_b.write_text("dummy")

            add_candidate("dl-exc-test", "https://example.com/a")
            add_candidate("dl-exc-test", "https://example.com/b")

            ok = BackendResult(
                status=SUCCESS,
                output_paths=[fake_b],
                attempts=[AttemptInfo(1, "yt-dlp", SUCCESS, 0, 1.0, False, "")],
            )
            with (
                patch(
                    "orchestrator.download_with_fallback",
                    side_effect=[RuntimeError("download boom"), (ok, "yt-dlp")],
                ),
                patch(
                    "orchestrator._validate_downloaded_file",
                    return_value=ProcessResult(0, "validated", "", status=SUCCESS),
                ),
            ):
                results = process_pending("dl-exc-test")

            assert results["failed"] == 1
            assert results["success"] == 1
            proj = load_project("dl-exc-test")
            a = next(t for t in proj.tasks if t.url == "https://example.com/a")
            b = next(t for t in proj.tasks if t.url == "https://example.com/b")
            assert a.status == "FAILED"
            assert b.status == "COMPLETED"
        finally:
            os.chdir(cwd)


def test_process_pending_validation_exception_fails_task():
    from unittest.mock import patch

    from _common import ensure_output_dir
    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult
    from project import create_project, load_project, save_project
    from safe_path import resolve_project_dir

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("val-exc-test")
            save_project(p)

            root = ensure_output_dir()
            pdir = resolve_project_dir(root, "val-exc-test")
            asset_dir = pdir / "assets" / "originals"
            asset_dir.mkdir(parents=True, exist_ok=True)
            fake = asset_dir / "v.ts"
            fake.write_text("dummy")

            add_candidate("val-exc-test", "https://example.com/v")
            be = BackendResult(status=SUCCESS, output_paths=[fake])
            with (
                patch("orchestrator.download_with_fallback", return_value=(be, "yt-dlp")),
                patch(
                    "orchestrator._validate_downloaded_file",
                    side_effect=RuntimeError("probe parse boom"),
                ),
            ):
                results = process_pending("val-exc-test")

            assert results["failed"] == 1
            assert results["success"] == 0
            proj = load_project("val-exc-test")
            assert proj.tasks[0].status == "FAILED"
        finally:
            os.chdir(cwd)


def test_source_json_not_finalized_when_complete_fails():
    from unittest.mock import patch

    from _common import ensure_output_dir
    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult, ProcessResult
    from project import create_project, load_project, save_project
    from safe_path import resolve_project_dir

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("commit-unit-test")
            save_project(p)

            root = ensure_output_dir()
            pdir = resolve_project_dir(root, "commit-unit-test")
            asset_dir = pdir / "assets" / "originals"
            asset_dir.mkdir(parents=True, exist_ok=True)
            fake = asset_dir / "c.ts"
            fake.write_text("dummy")

            add_candidate("commit-unit-test", "https://example.com/c")
            be = BackendResult(status=SUCCESS, output_paths=[fake])
            with (
                patch("orchestrator.download_with_fallback", return_value=(be, "yt-dlp")),
                patch(
                    "orchestrator._validate_downloaded_file",
                    return_value=ProcessResult(0, "validated", "", status=SUCCESS),
                ),
                patch("orchestrator.complete_task", side_effect=RuntimeError("persist boom")),
            ):
                results = process_pending("commit-unit-test")

            assert results["failed"] == 1
            assert results["success"] == 0
            proj = load_project("commit-unit-test")
            assert proj.tasks[0].status == "FAILED"

            sources_dir = pdir / "acquisition" / "sources"
            finalized = list(sources_dir.glob("*.json")) if sources_dir.is_dir() else []
            pending = list(sources_dir.glob("*.json.pending")) if sources_dir.is_dir() else []
            assert finalized == []
            assert pending == []
        finally:
            os.chdir(cwd)


def test_process_pending_recovers_orphaned_running():
    from unittest.mock import patch

    from _common import ensure_output_dir
    from orchestrator import process_pending
    from process_runner import SUCCESS, AttemptInfo, BackendResult, ProcessResult
    from project import DownloadTask, create_project, load_project, save_project
    from safe_path import resolve_project_dir

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("orphan-test")
            p.tasks.append(DownloadTask(url="https://example.com/o", status="RUNNING"))
            save_project(p)

            root = ensure_output_dir()
            pdir = resolve_project_dir(root, "orphan-test")
            asset_dir = pdir / "assets" / "originals"
            asset_dir.mkdir(parents=True, exist_ok=True)
            fake = asset_dir / "o.ts"
            fake.write_text("dummy")

            be = BackendResult(
                status=SUCCESS,
                output_paths=[fake],
                attempts=[AttemptInfo(1, "yt-dlp", SUCCESS, 0, 1.0, False, "")],
            )
            with (
                patch("orchestrator.download_with_fallback", return_value=(be, "yt-dlp")),
                patch(
                    "orchestrator._validate_downloaded_file",
                    return_value=ProcessResult(0, "validated", "", status=SUCCESS),
                ),
            ):
                results = process_pending("orphan-test")

            assert results["success"] == 1
            proj = load_project("orphan-test")
            assert proj.tasks[0].status == "COMPLETED"
        finally:
            os.chdir(cwd)


def test_finalize_source_json_failure_reverts_task_to_failed():
    from unittest.mock import patch

    from _common import ensure_output_dir
    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult, ProcessResult
    from project import create_project, load_project, save_project
    from safe_path import resolve_project_dir

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("finalize-fail-test")
            save_project(p)

            root = ensure_output_dir()
            pdir = resolve_project_dir(root, "finalize-fail-test")
            asset_dir = pdir / "assets" / "originals"
            asset_dir.mkdir(parents=True, exist_ok=True)
            fake = asset_dir / "f.ts"
            fake.write_text("dummy")

            add_candidate("finalize-fail-test", "https://example.com/f")
            be = BackendResult(status=SUCCESS, output_paths=[fake])
            with (
                patch("orchestrator.download_with_fallback", return_value=(be, "yt-dlp")),
                patch(
                    "orchestrator._validate_downloaded_file",
                    return_value=ProcessResult(0, "validated", "", status=SUCCESS),
                ),
                patch("orchestrator._finalize_source_json", return_value=None),
            ):
                results = process_pending("finalize-fail-test")

            assert results["failed"] == 1
            assert results["success"] == 0
            proj = load_project("finalize-fail-test")
            assert proj.tasks[0].status == "FAILED"

            sources_dir = pdir / "acquisition" / "sources"
            finalized = list(sources_dir.glob("*.json")) if sources_dir.is_dir() else []
            pending = list(sources_dir.glob("*.json.pending")) if sources_dir.is_dir() else []
            assert finalized == []
            assert pending == []
        finally:
            os.chdir(cwd)
