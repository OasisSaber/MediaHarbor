from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skill" / "untitled" / "scripts"))


def _setup_temp_project(tmp: str):
    root = Path(tmp)
    (root / "AGENT_READ_ME_FIRST.md").write_text("")
    (root / "download-tools").mkdir(parents=True)
    tjson = (
        '{"schema_version": 1, "tools": {"d": {"roles": ["t"], '
        '"platforms": {"windows-x64": "d/d.exe"}}}}'
    )
    (root / "download-tools" / "tools.json").write_text(tjson)
    (root / "skill" / "untitled").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "untitled" / "SKILL.md").write_text("---\ntitle: t\n---\n", encoding="utf-8")


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


def test_source_json_populates_story_node_id():
    from orchestrator import _build_source_entry
    from process_runner import BackendResult
    from project import Candidate, StoryNode, create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("story-node-source-test")
            node = StoryNode(title="节点A", description="发射素材")
            p.story_nodes.append(node)
            p.candidates.append(
                Candidate(
                    execution_url="https://example.com/v",
                    display_url="https://example.com/v",
                    state="ACCEPTED",
                    story_node_title="节点A",
                )
            )
            save_project(p)

            video = Path(tmp) / "output" / "story-node-source-test" / "assets" / "originals"
            video.mkdir(parents=True)
            test_file = video / "sample.mp4"
            test_file.write_bytes(b"fake media content for testing")

            entry = _build_source_entry(
                "story-node-source-test",
                "https://example.com/v",
                BackendResult(status="SUCCESS", output_paths=[test_file], attempts=[]),
                "yt-dlp",
                main_file=test_file,
            )
            assert entry is not None
            assert entry["story_node_id"] == node.node_id
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

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del format_selector
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

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del format_selector
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

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del format_selector
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

            def fake_download(url, output_dir, runner=None, format_selector=None):
                del format_selector
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


def test_validation_exception_fails_one_task_and_continues_queue():
    from unittest.mock import patch

    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult, ProcessResult
    from project import create_project, load_project, project_dir, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = f"queue-exception-{Path(tmp).name}"
            save_project(create_project(project_name))
            first_url = "https://example.com/first"
            second_url = "https://example.com/second"
            add_candidate(project_name, first_url)
            add_candidate(project_name, second_url)

            def fake_download(url, output_dir, runner=None, format_selector=None):
                del format_selector
                del runner
                media = output_dir / "video.mp4"
                media.write_text(url)
                return BackendResult(status=SUCCESS, output_paths=[media]), "yt-dlp"

            validation_success = ProcessResult(
                returncode=0,
                stdout="validated",
                stderr="",
                status=SUCCESS,
            )
            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch(
                    "orchestrator._validate_downloaded_file",
                    side_effect=[ValueError("malformed ffprobe fields"), validation_success],
                ),
            ):
                result = process_pending(project_name)

            assert result["processed"] == 2
            assert result["failed"] == 1
            assert result["success"] == 1
            project = load_project(project_name)
            statuses = {task.url: task.status for task in project.tasks}
            assert statuses == {
                first_url: "FAILED",
                second_url: "COMPLETED",
            }
            assert all(task.status != "RUNNING" for task in project.tasks)
            source_files = list(
                (project_dir(project_name) / "acquisition" / "sources").glob("*.json")
            )
            assert len(source_files) == 1
            source = json.loads(source_files[0].read_text(encoding="utf-8"))
            assert source["display_url"] == second_url
            assert source["final_status"] == "SUCCESS"
        finally:
            os.chdir(cwd)


def test_process_pending_recovers_interrupted_running_task():
    from acquisition import add_candidate, start_task
    from orchestrator import process_pending
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = f"interrupted-{Path(tmp).name}"
            url = "https://example.com/interrupted"
            save_project(create_project(project_name))
            add_candidate(project_name, url)
            start_task(project_name, url)
            assert load_project(project_name).tasks[0].status == "RUNNING"

            result = process_pending(project_name)

            task = load_project(project_name).tasks[0]
            assert result["recovered"] == 1
            assert task.status == "FAILED"
            assert "interrupted" in task.error.lower()
            assert task.completed_at is not None
        finally:
            os.chdir(cwd)


def test_project_commit_failure_leaves_no_success_source_or_final_artifact():
    from unittest.mock import patch

    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult, ProcessResult
    from project import create_project, load_project, project_dir, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = f"commit-failure-{Path(tmp).name}"
            url = "https://example.com/commit-failure"
            save_project(create_project(project_name))
            add_candidate(project_name, url)
            task_id = load_project(project_name).tasks[0].task_id

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del format_selector
                del runner
                media = output_dir / "video.mp4"
                media.write_text("media")
                return BackendResult(status=SUCCESS, output_paths=[media]), "yt-dlp"

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as validation,
                patch(
                    "orchestrator.complete_task",
                    side_effect=OSError("injected project commit failure"),
                ),
            ):
                validation.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                result = process_pending(project_name)

            project = load_project(project_name)
            assert result["failed"] == 1
            assert project.tasks[0].status == "FAILED"
            assert project.materials == []
            source_dir = project_dir(project_name) / "acquisition" / "sources"
            assert list(source_dir.glob("*.json")) == []
            final_dir = project_dir(project_name) / "assets" / "originals"
            assert list(final_dir.glob(f"{task_id}-*")) == []
        finally:
            os.chdir(cwd)


def test_completed_task_recovers_pending_source_transaction():
    from acquisition import add_candidate, complete_task, start_task
    from orchestrator import _stage_source_transaction, process_pending
    from project import create_project, load_project, project_dir, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = f"source-recovery-{Path(tmp).name}"
            url = "https://example.com/recover-source"
            save_project(create_project(project_name))
            add_candidate(project_name, url)
            task = start_task(project_name, url)
            artifact = project_dir(project_name) / "assets" / "originals" / "video.mp4"
            artifact.write_text("media")
            entry = {
                "source_id": f"source-{task.task_id}",
                "display_url": url,
                "final_status": "SUCCESS",
            }
            pending = _stage_source_transaction(
                project_name,
                task.task_id,
                entry,
                [artifact],
            )
            complete_task(project_name, url, "yt-dlp", [str(artifact)])

            result = process_pending(project_name)

            source = pending.parent / f"{entry['source_id']}.json"
            assert result["source_transactions_recovered"] == 1
            assert source.is_file()
            assert json.loads(source.read_text(encoding="utf-8")) == entry
            assert not pending.exists()
            assert load_project(project_name).tasks[0].status == "COMPLETED"
        finally:
            os.chdir(cwd)


def test_running_task_discards_uncommitted_source_and_artifact_on_recovery():
    from acquisition import add_candidate, start_task
    from orchestrator import _stage_source_transaction, process_pending
    from project import create_project, load_project, project_dir, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = f"source-rollback-{Path(tmp).name}"
            url = "https://example.com/rollback-source"
            save_project(create_project(project_name))
            add_candidate(project_name, url)
            task = start_task(project_name, url)
            artifact = project_dir(project_name) / "assets" / "originals" / "video.mp4"
            artifact.write_text("uncommitted media")
            entry = {
                "source_id": f"source-{task.task_id}",
                "display_url": url,
                "final_status": "SUCCESS",
            }
            pending = _stage_source_transaction(
                project_name,
                task.task_id,
                entry,
                [artifact],
            )

            result = process_pending(project_name)

            assert result["recovered"] == 1
            assert load_project(project_name).tasks[0].status == "FAILED"
            assert not pending.exists()
            assert not artifact.exists()
            assert not (pending.parent / f"{entry['source_id']}.json").exists()
        finally:
            os.chdir(cwd)


def test_execution_url_used_for_download():
    from unittest.mock import patch

    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, AttemptInfo, BackendResult, ProcessResult
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = "execution-url-test"
            save_project(create_project(project_name))
            raw_url = "https://example.com/video?signature=abc123&expires=9999999999"
            add_candidate(project_name, raw_url)

            captured: dict[str, str] = {}

            def fake_download(url, output_dir, runner=None, format_selector=None):
                del format_selector
                del runner
                captured["url"] = url
                fake_file = output_dir / "video.mp4"
                fake_file.write_bytes(b"fake media content")
                return (
                    BackendResult(
                        status=SUCCESS,
                        output_paths=[fake_file],
                        attempts=[
                            AttemptInfo(1, "yt-dlp", SUCCESS, 0, 1.0, False, ""),
                        ],
                    ),
                    "yt-dlp",
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
                results = process_pending(project_name)

            assert captured["url"] == raw_url
            assert results["success"] == 1
            task = load_project(project_name).tasks[0]
            assert task.status == "COMPLETED"
            assert task.execution_url == raw_url
        finally:
            os.chdir(cwd)


def test_legacy_sanitized_task_without_execution_url_fails():
    from orchestrator import process_pending
    from project import DownloadTask, create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = "legacy-sanitized-task"
            p = create_project(project_name)
            p.tasks.append(
                DownloadTask(
                    url="https://example.com/video?token=REDACTED",
                    execution_url=None,
                    status="PENDING",
                )
            )
            save_project(p)

            result = process_pending(project_name)

            task = load_project(project_name).tasks[0]
            assert result["processed"] == 1
            assert result["failed"] == 1
            assert task.status == "FAILED"
            assert task.error is not None
        finally:
            os.chdir(cwd)


def test_finalize_midway_failure_rolls_back_and_fails_task():
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
            project_name = "finalize-rollback-test"
            save_project(create_project(project_name))
            add_candidate(project_name, "https://example.com/live")
            task_id = load_project(project_name).tasks[0].task_id

            root = ensure_output_dir()
            project_dir = resolve_project_dir(root, project_name)
            final_dir = project_dir / "assets" / "originals"
            final_dir.mkdir(parents=True, exist_ok=True)
            stale = final_dir / f"{task_id}-stream.ts"
            stale.write_text("existing material")

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del format_selector
                del runner
                output_dir.mkdir(parents=True, exist_ok=True)
                main = output_dir / "stream.ts"
                subtitle = output_dir / "stream.en.vtt"
                main.write_text("new media")
                subtitle.write_text("new subtitle")
                return BackendResult(status=SUCCESS, output_paths=[main, subtitle]), "streamlink"

            real_move = shutil.move
            move_calls = {"count": 0}

            def failing_move(src, dst):
                move_calls["count"] += 1
                if move_calls["count"] == 2:
                    raise OSError("simulated move failure on second file")
                return real_move(src, dst)

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as mock_validate,
                patch("orchestrator.shutil.move", side_effect=failing_move),
            ):
                mock_validate.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                result = process_pending(project_name)

            assert result["failed"] == 1
            task = load_project(project_name).tasks[0]
            assert task.status == "FAILED"
            assert "FINALIZATION_FAILED" in task.error
            assert stale.read_text() == "existing material"
            names = {p.name for p in final_dir.iterdir()}
            assert f"{task_id}-stream.ts" in names
            assert f"{task_id}-2-stream.ts" not in names
            assert f"{task_id}-stream.en.vtt" not in names
        finally:
            os.chdir(cwd)


def test_finalize_rollback_failure_removes_partial_files():
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
            project_name = "finalize-rollback-fail-test"
            save_project(create_project(project_name))
            add_candidate(project_name, "https://example.com/live")
            task_id = load_project(project_name).tasks[0].task_id

            root = ensure_output_dir()
            project_dir = resolve_project_dir(root, project_name)
            final_dir = project_dir / "assets" / "originals"
            final_dir.mkdir(parents=True, exist_ok=True)

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del format_selector
                del runner
                output_dir.mkdir(parents=True, exist_ok=True)
                main = output_dir / "stream.ts"
                subtitle = output_dir / "stream.en.vtt"
                main.write_text("new media")
                subtitle.write_text("new subtitle")
                return BackendResult(status=SUCCESS, output_paths=[main, subtitle]), "streamlink"

            real_move = shutil.move
            move_calls = {"count": 0}

            def move_then_always_fail(src, dst):
                move_calls["count"] += 1
                if move_calls["count"] == 1:
                    return real_move(src, dst)
                raise OSError("simulated persistent move failure")

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as mock_validate,
                patch("orchestrator.shutil.move", side_effect=move_then_always_fail),
            ):
                mock_validate.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                result = process_pending(project_name)

            assert result["failed"] == 1
            task = load_project(project_name).tasks[0]
            assert task.status == "FAILED"
            assert "FINALIZATION_FAILED" in task.error
            assert "rollback was incomplete" in task.error
            names = {p.name for p in final_dir.iterdir()}
            assert not any(name.startswith(task_id) for name in names)
        finally:
            os.chdir(cwd)


def test_completed_task_survives_source_commit_failure():
    from unittest.mock import patch

    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult, ProcessResult
    from project import create_project, load_project, project_dir, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = f"source-commit-failure-{Path(tmp).name}"
            url = "https://example.com/commit-late-failure"
            save_project(create_project(project_name))
            add_candidate(project_name, url)
            task_id = load_project(project_name).tasks[0].task_id

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del format_selector
                del runner
                media = output_dir / "video.mp4"
                media.write_text("media")
                return BackendResult(status=SUCCESS, output_paths=[media]), "yt-dlp"

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as validation,
                patch(
                    "orchestrator._commit_source_transaction",
                    side_effect=OSError("injected source commit failure"),
                ),
            ):
                validation.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                result = process_pending(project_name)

            project = load_project(project_name)
            task = project.tasks[0]
            assert result["success"] == 1
            assert result["failed"] == 0
            assert task.status == "COMPLETED"
            assert len(project.materials) == 1
            assert result["details"][0]["source_pending"] is True
            assert result["details"][0]["source_pending_error"]

            source_dir = project_dir(project_name) / "acquisition" / "sources"
            pending = source_dir / f"{task_id}.source.pending"
            assert pending.is_file()

            recovered = process_pending(project_name)
            assert recovered["source_transactions_recovered"] == 1
            assert not pending.exists()
            assert list(source_dir.glob("*.json"))
        finally:
            os.chdir(cwd)


def test_source_json_populated_from_candidate_metadata():
    import json as _json
    from unittest.mock import patch

    from acquisition import preflight_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult, ProcessResult
    from project import create_project, project_dir, save_project

    probe_json = _json.dumps(
        {
            "id": "BVsrc",
            "title": "Official archive recording",
            "extractor": "BiliBili",
            "uploader": "National Archive",
            "upload_date": "20260101",
            "duration": 1800.0,
            "is_live": False,
            "formats": [{"height": 1080}],
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = f"source-fill-{Path(tmp).name}"
            save_project(create_project(project_name))
            with patch(
                "ytdlp_adapter.probe_url",
                return_value=ProcessResult(
                    returncode=0, stdout=probe_json, stderr="", status=SUCCESS
                ),
            ):
                candidate = preflight_candidate(
                    project_name, "https://example.com/video?id=1", search_query="archival"
                )
            assert candidate.state == "ACCEPTED"

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del format_selector
                del runner
                media = output_dir / "video.mp4"
                media.write_text("media")
                return BackendResult(status=SUCCESS, output_paths=[media]), "yt-dlp"

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as validation,
            ):
                validation.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                results = process_pending(project_name)

            assert results["success"] == 1
            source_dir = project_dir(project_name) / "acquisition" / "sources"
            sources = list(source_dir.glob("*.json"))
            assert len(sources) == 1
            data = _json.loads(sources[0].read_text(encoding="utf-8"))
            assert data["platform"] == "BiliBili"
            assert data["platform_media_id"] == "BVsrc"
            assert data["title"] == "Official archive recording"
            assert data["uploader"] == "National Archive"
            assert data["publish_date"] == "20260101"
            assert data["duration"] == 1800.0
            assert data["search_query"] == "archival"
        finally:
            os.chdir(cwd)


def test_process_pending_rejects_no_qualifying_format_before_download():
    import json as _json
    from unittest.mock import patch

    from acquisition import preflight_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, ProcessResult
    from project import create_project, load_project, save_project

    probe_json = _json.dumps(
        {
            "id": "BVlow",
            "title": "Official archive recording",
            "extractor": "BiliBili",
            "uploader": "National Archive",
            "duration": 1800.0,
            "is_live": False,
            "formats": [{"height": 360, "fps": 24}],
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = f"quality-gate-{Path(tmp).name}"
            save_project(create_project(project_name))
            with patch(
                "ytdlp_adapter.probe_url",
                return_value=ProcessResult(
                    returncode=0, stdout=probe_json, stderr="", status=SUCCESS
                ),
            ):
                candidate = preflight_candidate(project_name, "https://example.com/low")
            assert candidate.state == "ACCEPTED"

            called = {"download": False}

            def fake_download(_url, _output_dir, runner=None, format_selector=None):
                del runner, format_selector
                called["download"] = True
                raise AssertionError("download must not run")

            with patch("orchestrator.download_with_fallback", side_effect=fake_download):
                results = process_pending(project_name)

            assert called["download"] is False
            assert results["failed"] == 1
            task = load_project(project_name).tasks[0]
            assert "NO_QUALIFYING_FORMAT" in task.error
        finally:
            os.chdir(cwd)


def test_process_pending_sets_quality_status_from_ffprobe():
    import json as _json
    from unittest.mock import patch

    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult, ProcessResult
    from project import create_project, load_project, save_project

    ffprobe_json = _json.dumps(
        {
            "format": {"format_name": "mp4", "duration": "30.0", "size": "100"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 640,
                    "height": 360,
                    "avg_frame_rate": "30/1",
                }
            ],
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = f"quality-post-{Path(tmp).name}"
            save_project(create_project(project_name))
            add_candidate(project_name, "https://example.com/lowres")

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del runner, format_selector
                media = output_dir / "video.mp4"
                media.write_text("media")
                return BackendResult(status=SUCCESS, output_paths=[media]), "yt-dlp"

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as validation,
            ):
                validation.return_value = ProcessResult(
                    returncode=0,
                    stdout=ffprobe_json,
                    stderr="",
                    status=SUCCESS,
                )
                results = process_pending(project_name)

            assert results["success"] == 1
            material = load_project(project_name).materials[0]
            assert material.quality_status == "REJECT"
            assert any("height" in r for r in material.quality_reasons)
            assert material.technical_status == "PASS"
        finally:
            os.chdir(cwd)


def test_visual_risk_sets_editorial_review_required():
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
            project_name = f"visual-risk-{Path(tmp).name}"
            save_project(create_project(project_name))
            add_candidate(project_name, "https://example.com/risk")

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del runner, format_selector
                media = output_dir / "video.mp4"
                media.write_text("media")
                return BackendResult(status=SUCCESS, output_paths=[media]), "yt-dlp"

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as validation,
                patch("orchestrator.analyze_media") as mock_analyze,
            ):
                validation.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                mock_analyze.return_value = {
                    "status": "PERSISTENT_SUBTITLES",
                    "labels": [{"label": "PERSISTENT_SUBTITLES", "score": 0.8, "confidence": 0.8}],
                    "metrics": {"subtitle_persistence": 1.0},
                    "ocr_status": "heuristic",
                }
                results = process_pending(project_name)

            assert results["success"] == 1
            material = load_project(project_name).materials[0]
            assert material.editorial_status == "REVIEW_REQUIRED"
            assert any("PERSISTENT_SUBTITLES" in r for r in material.editorial_reasons)
            assert material.visual_analysis["status"] == "PERSISTENT_SUBTITLES"
        finally:
            os.chdir(cwd)


def test_visual_analysis_unavailable_does_not_block():
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
            project_name = f"visual-unavailable-{Path(tmp).name}"
            save_project(create_project(project_name))
            add_candidate(project_name, "https://example.com/clean")

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del runner, format_selector
                media = output_dir / "video.mp4"
                media.write_text("media")
                return BackendResult(status=SUCCESS, output_paths=[media]), "yt-dlp"

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as validation,
                patch("orchestrator.analyze_media") as mock_analyze,
            ):
                validation.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                mock_analyze.return_value = {
                    "status": "ANALYSIS_UNAVAILABLE",
                    "labels": [],
                    "metrics": {},
                    "ocr_status": "unavailable",
                    "note": "ffmpeg unavailable",
                }
                results = process_pending(project_name)

            assert results["success"] == 1
            material = load_project(project_name).materials[0]
            assert material.editorial_status == "REVIEW_REQUIRED"
            assert "visual-analysis-unavailable" in material.editorial_reasons
        finally:
            os.chdir(cwd)


def test_clean_visual_analysis_keeps_unreviewed():
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
            project_name = f"visual-clean-{Path(tmp).name}"
            save_project(create_project(project_name))
            add_candidate(project_name, "https://example.com/clean2")

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del runner, format_selector
                media = output_dir / "video.mp4"
                media.write_text("media")
                return BackendResult(status=SUCCESS, output_paths=[media]), "yt-dlp"

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as validation,
                patch("orchestrator.analyze_media") as mock_analyze,
            ):
                validation.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                mock_analyze.return_value = {
                    "status": "CLEAN",
                    "labels": [],
                    "metrics": {"frames_analyzed": 6},
                    "ocr_status": "heuristic",
                }
                results = process_pending(project_name)

            assert results["success"] == 1
            material = load_project(project_name).materials[0]
            assert material.editorial_status == "UNREVIEWED"
            assert material.editorial_reasons == []
        finally:
            os.chdir(cwd)


def test_process_pending_with_danmaku_artifact_succeeds():
    from unittest.mock import patch

    from _common import ensure_output_dir
    from acquisition import add_candidate
    from orchestrator import process_pending
    from process_runner import SUCCESS, BackendResult, ProcessResult
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            project_name = f"danmaku-task-{Path(tmp).name}"
            save_project(create_project(project_name))
            add_candidate(project_name, "https://www.bilibili.com/video/BV1danmaku")
            task_id = load_project(project_name).tasks[0].task_id

            def fake_download(_url, output_dir, runner=None, format_selector=None):
                del runner, format_selector
                output_dir.mkdir(parents=True, exist_ok=True)
                media = output_dir / "BiliBili-BV1danmaku.mp4"
                media.write_text("media")
                danmaku = output_dir / "BiliBili-BV1danmaku.danmaku.xml"
                danmaku.write_text("<d><d p='1'>x</d></d>")
                return BackendResult(status=SUCCESS, output_paths=[media, danmaku]), "yt-dlp"

            with (
                patch("orchestrator.download_with_fallback", side_effect=fake_download),
                patch("orchestrator._validate_downloaded_file") as validation,
            ):
                validation.return_value = ProcessResult(
                    returncode=0,
                    stdout="validated",
                    stderr="",
                    status=SUCCESS,
                )
                results = process_pending(project_name)

            assert results["success"] == 1
            assert results["failed"] == 0
            project = load_project(project_name)
            task = project.tasks[0]
            assert task.status == "COMPLETED"
            assert len(project.materials) == 1
            assert project.materials[0].local_path.endswith(".mp4")
            originals = ensure_output_dir() / project_name / "assets" / "originals"
            originals_files = {p.name for p in originals.iterdir()}
            assert any(
                name.startswith(task_id) and name.endswith(".mp4") for name in originals_files
            )
            assert any(name.endswith(".danmaku.xml") for name in originals_files)
        finally:
            os.chdir(cwd)
