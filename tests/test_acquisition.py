from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skill" / "untitled" / "scripts"))


def _setup_temp_project(tmp: str):
    root = Path(tmp)
    (root / "AGENT_READ_ME_FIRST.md").write_text("")
    (root / "download-tools").mkdir(parents=True)
    tools_json = (
        '{"schema_version": 1, "tools": {"dummy": {"roles": ["test"], '
        '"platforms": {"windows-x64": "dummy/dummy.exe"}}}}'
    )
    (root / "download-tools" / "tools.json").write_text(tools_json)
    (root / "skill" / "untitled").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "untitled" / "SKILL.md").write_text(
        "---\ntitle: test\n---\n", encoding="utf-8"
    )


def test_add_candidate():
    from acquisition import add_candidate
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("acq-test")
            save_project(p)
            result = add_candidate("acq-test", "https://example.com/video1")
            assert result is not None
            assert len(result.tasks) == 1
            assert result.tasks[0].url == "https://example.com/video1"
            assert result.tasks[0].status == "PENDING"
        finally:
            os.chdir(cwd)


def test_start_and_complete_task():
    from acquisition import add_candidate, complete_task, start_task
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("task-test")
            save_project(p)
            add_candidate("task-test", "https://example.com/vid")
            started = start_task("task-test", "https://example.com/vid")
            assert started is not None
            assert started.status == "RUNNING"
            completed = complete_task(
                "task-test", "https://example.com/vid", "yt-dlp", ["output/task-test/video.mp4"]
            )
            assert completed is not None
            assert completed.status == "COMPLETED"
        finally:
            os.chdir(cwd)


def test_complete_task_nonexistent():
    from acquisition import complete_task
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("nonexist-test")
            save_project(p)
            result = complete_task(
                "nonexist-test", "https://no-such-url.com", "yt-dlp", ["output/fake.mp4"]
            )
            assert result is None
        finally:
            os.chdir(cwd)


def test_complete_task_empty_paths():
    import pytest
    from acquisition import add_candidate, complete_task, start_task
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("empty-test")
            save_project(p)
            add_candidate("empty-test", "https://example.com/vid")
            start_task("empty-test", "https://example.com/vid")
            with pytest.raises(ValueError, match="output_paths"):
                complete_task("empty-test", "https://example.com/vid", "yt-dlp", [])
        finally:
            os.chdir(cwd)


def test_complete_task_is_idempotent_for_material_registration():
    from acquisition import add_candidate, complete_task, start_task
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            save_project(create_project("idempotent-task"))
            url = "https://example.com/video"
            add_candidate("idempotent-task", url)
            start_task("idempotent-task", url)

            complete_task("idempotent-task", url, "yt-dlp", ["video.mp4"])
            complete_task("idempotent-task", url, "yt-dlp", ["video.mp4"])

            assert len(load_project("idempotent-task").materials) == 1
        finally:
            os.chdir(cwd)


def test_fail_task():
    from acquisition import add_candidate, fail_task, start_task
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("fail-test")
            save_project(p)
            add_candidate("fail-test", "https://example.com/bad")
            start_task("fail-test", "https://example.com/bad")
            failed = fail_task("fail-test", "https://example.com/bad", "DRM detected")
            assert failed is not None
            assert failed.status == "FAILED"
        finally:
            os.chdir(cwd)


def test_retry_failed_task():
    from acquisition import add_candidate, fail_task, retry_task, start_task
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("retry-test")
            save_project(p)
            add_candidate("retry-test", "https://example.com/retry")
            start_task("retry-test", "https://example.com/retry")
            fail_task("retry-test", "https://example.com/retry", "timeout")
            retried = retry_task("retry-test", "https://example.com/retry")
            assert retried is not None
            assert retried.status == "PENDING"
            assert retried.error is None
        finally:
            os.chdir(cwd)


def test_get_pending_tasks():
    from acquisition import add_candidate, get_pending_tasks
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("pending-test")
            save_project(p)
            add_candidate("pending-test", "https://example.com/v1")
            add_candidate("pending-test", "https://example.com/v2")
            pending = get_pending_tasks("pending-test")
            assert len(pending) == 2
        finally:
            os.chdir(cwd)


def test_sanitized_url_persisted():
    from acquisition import add_candidate
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("sanitize-test")
            save_project(p)
            url_with_token = "https://example.com/video?token=secret123&q=hello"
            r = add_candidate("sanitize-test", url_with_token)
            assert r is not None
            assert r.tasks[0].url != url_with_token
            assert "REDACTED" in r.tasks[0].url
            assert "hello" in r.tasks[0].url
            assert r.tasks[0].execution_url == url_with_token
        finally:
            os.chdir(cwd)


def test_execution_url_preserved_for_signed_url():
    from acquisition import add_candidate
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("signed-url-test")
            save_project(p)
            signed = (
                "https://example.com/video?id=123&signature=abc123&expires=9999999999&"
                "X-Amz-Credential=credential-value"
            )
            r = add_candidate("signed-url-test", signed)
            assert r is not None
            task = r.tasks[0]
            assert task.execution_url == signed
            assert task.url != signed
            assert "REDACTED" in task.url
            assert "abc123" not in task.url
            assert "credential-value" not in task.url
        finally:
            os.chdir(cwd)


def test_display_url_truncates_long_non_sensitive_params():
    from acquisition import add_candidate
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("long-param-test")
            save_project(p)
            long_value = "a" * 500
            url = f"https://example.com/v?cursor={long_value}&id=1"
            r = add_candidate("long-param-test", url)
            assert r is not None
            display = r.tasks[0].url
            assert display.startswith("https://example.com/v?")
            assert "cursor" in display
            assert len(display) < len(url)
            assert r.tasks[0].execution_url == url
        finally:
            os.chdir(cwd)


def test_clean_url_passthrough():
    from acquisition import add_candidate
    from project import create_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("clean-test")
            save_project(p)
            r = add_candidate("clean-test", "https://example.com/v?id=1")
            assert len(r.tasks) == 1
            assert r.tasks[0].url == "https://example.com/v?id=1"
        finally:
            os.chdir(cwd)


def test_preflight_probe_failure_holds_candidate():
    from unittest.mock import patch

    from acquisition import preflight_candidate
    from process_runner import ProcessResult
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("preflight-fail-test")
            save_project(p)
            with patch(
                "ytdlp_adapter.probe_url",
                return_value=ProcessResult(
                    returncode=-1, stdout="", stderr="yt-dlp not found", status="TOOL_MISSING"
                ),
            ):
                candidate = preflight_candidate(
                    "preflight-fail-test", "https://example.com/video?id=1"
                )
            assert candidate is not None
            assert candidate.state == "FAILED_PROBE"
            assert candidate.probe_error
            project = load_project("preflight-fail-test")
            assert len(project.candidates) == 1
            assert len(project.tasks) == 0
        finally:
            os.chdir(cwd)


def test_preflight_accepts_high_provenance_and_enqueues():
    import json as _json
    from unittest.mock import patch

    from acquisition import preflight_candidate
    from process_runner import ProcessResult
    from project import create_project, load_project, save_project

    probe_json = _json.dumps(
        {
            "id": "BV1abc",
            "title": "Official archive recording",
            "extractor": "BiliBili",
            "uploader": "National Archive",
            "upload_date": "20260101",
            "duration": 1800.0,
            "is_live": False,
            "formats": [{"height": 1080, "fps": 30, "tbr": 5000.0}],
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("preflight-accept-test")
            save_project(p)
            with patch(
                "ytdlp_adapter.probe_url",
                return_value=ProcessResult(
                    returncode=0, stdout=probe_json, stderr="", status="SUCCESS"
                ),
            ):
                candidate = preflight_candidate(
                    "preflight-accept-test",
                    "https://example.com/video?id=1",
                    search_query="archival footage",
                    node_title="Intro",
                )
            assert candidate is not None
            assert candidate.state == "ACCEPTED"
            assert candidate.platform_media_id == "BV1abc"
            assert candidate.title == "Official archive recording"
            assert candidate.uploader == "National Archive"
            assert candidate.publish_date == "20260101"
            assert candidate.format_summary["max_height"] == 1080
            assert candidate.provenance_score is not None
            project = load_project("preflight-accept-test")
            assert len(project.candidates) == 1
            assert len(project.tasks) == 1
            assert project.tasks[0].execution_url == "https://example.com/video?id=1"
        finally:
            os.chdir(cwd)


def test_preflight_rejects_low_provenance_without_override():
    import json as _json
    from unittest.mock import patch

    from acquisition import preflight_candidate
    from process_runner import ProcessResult
    from project import create_project, load_project, save_project

    probe_json = _json.dumps(
        {
            "id": "BV2xyz",
            "title": "Reaction and commentary of the event",
            "extractor": "BiliBili",
            "uploader": "Fan Channel",
            "duration": 30.0,
            "is_live": False,
            "formats": [],
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("preflight-reject-test")
            save_project(p)
            with patch(
                "ytdlp_adapter.probe_url",
                return_value=ProcessResult(
                    returncode=0, stdout=probe_json, stderr="", status="SUCCESS"
                ),
            ):
                candidate = preflight_candidate(
                    "preflight-reject-test", "https://example.com/video?id=2"
                )
            assert candidate is not None
            assert candidate.state == "REJECTED"
            assert candidate.rejection_reasons == ["below-provenance-threshold"]
            project = load_project("preflight-reject-test")
            assert len(project.candidates) == 1
            assert len(project.tasks) == 0
        finally:
            os.chdir(cwd)


def test_preflight_duplicate_media_id_rejected_and_override_enqueues():
    import json as _json
    from unittest.mock import patch

    from acquisition import preflight_candidate
    from process_runner import ProcessResult
    from project import Candidate, create_project, load_project, save_project

    probe_json = _json.dumps(
        {
            "id": "BVdup",
            "title": "Official recording",
            "extractor": "BiliBili",
            "uploader": "National Archive",
            "duration": 1800.0,
            "is_live": False,
            "formats": [],
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("preflight-dup-test")
            p.candidates.append(
                Candidate(
                    execution_url="https://example.com/old",
                    display_url="https://example.com/old",
                    platform_media_id="BVdup",
                    state="ACCEPTED",
                )
            )
            save_project(p)
            with patch(
                "ytdlp_adapter.probe_url",
                return_value=ProcessResult(
                    returncode=0, stdout=probe_json, stderr="", status="SUCCESS"
                ),
            ):
                candidate = preflight_candidate("preflight-dup-test", "https://example.com/new")
                assert candidate is not None
                assert candidate.state == "REJECTED"
                assert "duplicate-platform-media-id" in candidate.rejection_reasons

                overridden = preflight_candidate(
                    "preflight-dup-test", "https://example.com/new2", override=True
                )
                assert overridden is not None
                assert overridden.state == "ACCEPTED"
                assert overridden.overridden is True
            project = load_project("preflight-dup-test")
            assert len(project.tasks) == 1
        finally:
            os.chdir(cwd)


def test_complete_task_sets_conservative_assessment_states():
    from acquisition import add_candidate, complete_task, start_task
    from project import create_project, load_project, save_project

    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_project(tmp)
        cwd = Path.cwd()
        try:
            os.chdir(tmp)
            p = create_project("assessment-task-test")
            save_project(p)
            url = "https://example.com/assess"
            add_candidate("assessment-task-test", url)
            start_task("assessment-task-test", url)
            complete_task(
                "assessment-task-test",
                url,
                "yt-dlp",
                ["output/assessment-task-test/video.mp4"],
            )
            project = load_project("assessment-task-test")
            material = project.materials[0]
            assert material.technical_status == "PASS"
            assert material.quality_status == "UNKNOWN"
            assert material.editorial_status == "UNREVIEWED"
            assert material.assessment_timestamp is not None
        finally:
            os.chdir(cwd)
