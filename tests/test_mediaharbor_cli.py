from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "mediaharbor.py"


def _setup_temp_workspace(tmp: str) -> None:
    root = Path(tmp)
    (root / "AGENT_READ_ME_FIRST.md").write_text("")
    (root / "download-tools").mkdir(parents=True, exist_ok=True)
    tools_json = (
        '{"schema_version": 1, "tools": {"dummy": {"roles": ["test"], '
        '"platforms": {"windows-x64": "dummy/dummy.exe"}}}}'
    )
    (root / "download-tools" / "tools.json").write_text(tools_json)
    (root / "skill" / "mediaharbor").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "mediaharbor" / "SKILL.md").write_text(
        "---\ntitle: test\n---\n", encoding="utf-8"
    )


def _unique_project(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _cleanup_project(project_name: str) -> None:
    project_dir = REPO_ROOT / "output" / project_name
    if project_dir.is_dir():
        shutil.rmtree(project_dir, ignore_errors=True)


def _run_cli(cwd: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _load_json(result: subprocess.CompletedProcess) -> dict:
    assert result.returncode in (0, 1), f"unexpected exit {result.returncode}: {result.stderr}"
    return json.loads(result.stdout)


def test_check_tools_output_shape():
    result = _run_cli(str(REPO_ROOT), "check-tools", "--json")
    payload = _load_json(result)
    assert set(payload) == {"ok", "status", "data", "error"}
    assert payload["ok"] is True
    assert payload["status"] in ("READY", "DEGRADED")
    assert "tools" in payload["data"]
    assert payload["error"] is None


def test_project_create_and_status_roundtrip():
    project_name = _unique_project("cli-project")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _setup_temp_workspace(tmp)
            result = _run_cli(tmp, "project-create", project_name, "--json")
            payload = _load_json(result)
            assert payload["ok"] is True
            assert payload["data"]["name"] == project_name

            result = _run_cli(tmp, "status", project_name, "--json")
            payload = _load_json(result)
            assert payload["ok"] is True
            assert payload["data"]["tasks"] == []
            assert payload["data"]["materials"] == []
    finally:
        _cleanup_project(project_name)


def test_candidate_add_and_process_flow():
    project_name = _unique_project("cli-flow")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _setup_temp_workspace(tmp)
            _run_cli(tmp, "project-create", project_name, "--json")

            result = _run_cli(
                tmp, "candidate-add", project_name, "https://example.com/video", "--json"
            )
            payload = _load_json(result)
            assert payload["ok"] is True
            assert payload["data"]["status"] == "PENDING"

            result = _run_cli(tmp, "process", project_name, "--json")
            payload = _load_json(result)
            assert set(payload) == {"ok", "status", "data", "error"}
            assert payload["data"]["processed"] == 1
            assert payload["data"]["failed"] == 1
            assert payload["ok"] is False
            assert payload["status"] == "FAILED"

            result = _run_cli(tmp, "status", project_name, "--json")
            payload = _load_json(result)
            assert payload["data"]["tasks"][0]["status"] == "FAILED"
    finally:
        _cleanup_project(project_name)


def test_candidate_add_missing_project():
    project_name = _unique_project("cli-missing")
    with tempfile.TemporaryDirectory() as tmp:
        _setup_temp_workspace(tmp)
        result = _run_cli(tmp, "candidate-add", project_name, "https://example.com/v", "--json")
        payload = _load_json(result)
        assert payload["ok"] is False
        assert payload["status"] == "PROJECT_NOT_FOUND"
        assert payload["error"]


def test_run_composite_command():
    project_name = _unique_project("cli-run")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _setup_temp_workspace(tmp)
            result = _run_cli(
                tmp,
                "run",
                "--project",
                project_name,
                "--url",
                "https://example.com/video",
                "--json",
            )
            payload = _load_json(result)
            assert set(payload) == {"ok", "status", "data", "error"}
            assert payload["data"]["processed"] == 1
            assert payload["status"] in ("FAILED", "PARTIAL")
    finally:
        _cleanup_project(project_name)


def test_unknown_command_fails():
    result = _run_cli(str(REPO_ROOT), "no-such-command")
    assert result.returncode == 2
