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
