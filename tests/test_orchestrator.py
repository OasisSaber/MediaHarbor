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


def test_validate_downloaded_file_missing(tmp_path):
    from orchestrator import _validate_downloaded_file

    result = _validate_downloaded_file(tmp_path / "missing.mp4", tmp_path)
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


def test_generate_source_json_nonexistent_project(tmp_path):
    from orchestrator import _generate_source_json
    from process_runner import BackendResult

    fake_file = tmp_path / "fake.mp4"
    result = _generate_source_json(
        "nonexistent-project",
        "https://example.com/v",
        BackendResult(status="SUCCESS", output_paths=[fake_file]),
        "yt-dlp",
        main_file=fake_file,
    )
    assert result is None


def test_process_pending_streamlink_success():
    from unittest.mock import patch

    from _common import ensure_output_dir
    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, AttemptInfo, BackendResult, ProcessResult
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("streamlink-success-test")
            save_project(p)

            add_candidate("streamlink-success-test", "https://example.com/live")
            task_id = load_project("streamlink-success-test").tasks[0].task_id

            def fake_download(_url, output_dir, runner=None):
                del runner
                fake_file = output_dir / "stream.ts"
                fake_file.write_text("dummy media content")
                return (
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

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as mock_val,
            ):
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
                final_file = (
                    ensure_output_dir()
                    / "streamlink-success-test"
                    / "assets"
                    / "originals"
                    / f"{task_id}-stream.ts"
                )
                assert proj.tasks[0].output_paths == [str(final_file)]
        finally:
            os.chdir(cwd)


def test_process_pending_isolates_and_finalizes_task_artifacts():
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
            project_name = "artifact-isolation-test"
            save_project(create_project(project_name))
            add_candidate(project_name, "https://example.com/live")
            task_id = load_project(project_name).tasks[0].task_id

            root = ensure_output_dir()
            project_dir = resolve_project_dir(root, project_name)
            final_dir = project_dir / "assets" / "originals"
            final_dir.mkdir(parents=True, exist_ok=True)
            stale = final_dir / "stream.ts"
            stale.write_text("existing material")

            def fake_download(_url, output_dir, runner=None):
                del runner
                output_dir.mkdir(parents=True, exist_ok=True)
                main = output_dir / "stream.ts"
                subtitle = output_dir / "stream.en.vtt"
                main.write_text("new media")
                subtitle.write_text("new subtitle")
                return (
                    BackendResult(
                        status=SUCCESS,
                        output_paths=[main, subtitle],
                    ),
                    "streamlink",
                )

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as mock_validate,
            ):
                mock_validate.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                result = process_pending(project_name)

            assert result["success"] == 1
            assert result["failed"] == 0
            assert stale.read_text() == "existing material"

            finalized_main = final_dir / f"{task_id}-stream.ts"
            finalized_subtitle = final_dir / f"{task_id}-stream.en.vtt"
            assert finalized_main.read_text() == "new media"
            assert finalized_subtitle.read_text() == "new subtitle"

            project = load_project(project_name)
            assert project.tasks[0].output_paths == [
                str(finalized_main),
                str(finalized_subtitle),
            ]
            assert [material.local_path for material in project.materials] == [str(finalized_main)]
            assert not (project_dir / "assets" / ".staging" / task_id).exists()
        finally:
            os.chdir(cwd)


def test_process_pending_hashes_each_main_media_independently():
    import hashlib
    from unittest.mock import patch

    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult, ProcessResult
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = "multi-main-test"
            save_project(create_project(project_name))
            add_candidate(project_name, "https://example.com/playlist")

            contents = {
                "first.mp4": b"first media",
                "second.mp4": b"second media",
            }

            def fake_download(_url, output_dir, runner=None):
                del runner
                output_dir.mkdir(parents=True, exist_ok=True)
                paths = []
                for name, content in contents.items():
                    path = output_dir / name
                    path.write_bytes(content)
                    paths.append(path)
                return BackendResult(status=SUCCESS, output_paths=paths), "yt-dlp"

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as mock_validate,
            ):
                mock_validate.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                result = process_pending(project_name)

            assert result["success"] == 1
            assert mock_validate.call_count == 2
            project = load_project(project_name)
            assert len(project.materials) == 2
            actual_hashes = {
                Path(material.local_path).name.split("-", 1)[1]: material.file_hash
                for material in project.materials
            }
            expected_hashes = {
                name: hashlib.sha256(content).hexdigest() for name, content in contents.items()
            }
            assert actual_hashes == expected_hashes
        finally:
            os.chdir(cwd)


def test_consecutive_streamlink_tasks_keep_distinct_artifacts():
    from unittest.mock import patch

    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult, ProcessResult
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = "two-streams-test"
            save_project(create_project(project_name))
            add_candidate(project_name, "https://example.com/live/one")
            add_candidate(project_name, "https://example.com/live/two")

            def fake_download(url, output_dir, runner=None):
                del runner
                stream = output_dir / "stream.ts"
                stream.write_text(url)
                return BackendResult(status=SUCCESS, output_paths=[stream]), "streamlink"

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as mock_validate,
            ):
                mock_validate.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                result = process_pending(project_name)

            assert result["success"] == 2
            project = load_project(project_name)
            material_paths = [Path(material.local_path) for material in project.materials]
            assert len(material_paths) == 2
            assert len(set(material_paths)) == 2
            assert {path.read_text() for path in material_paths} == {
                "https://example.com/live/one",
                "https://example.com/live/two",
            }
        finally:
            os.chdir(cwd)
