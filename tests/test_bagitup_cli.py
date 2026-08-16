from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "bagitup.py"


def _setup_temp_workspace(tmp: str) -> None:
    root = Path(tmp)
    (root / "AGENT_READ_ME_FIRST.md").write_text("")
    (root / "download-tools").mkdir(parents=True, exist_ok=True)
    tools_json = (
        '{"schema_version": 1, "tools": {"dummy": {"roles": ["test"], '
        '"platforms": {"windows-x64": "dummy/dummy.exe"}}}}'
    )
    (root / "download-tools" / "tools.json").write_text(tools_json)
    (root / "skill" / "bagitup").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "bagitup" / "SKILL.md").write_text(
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
        encoding="utf-8",
        cwd=cwd,
    )


def _load_json(result: subprocess.CompletedProcess) -> dict:
    assert result.returncode in (0, 1), f"unexpected exit {result.returncode}: {result.stderr}"
    return json.loads(result.stdout)


def test_story_node_add_and_list():
    project_name = _unique_project("cli-story")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _setup_temp_workspace(tmp)
            result = _run_cli(tmp, "project-create", project_name, "--json")
            assert _load_json(result)["ok"] is True

            result = _run_cli(
                tmp,
                "story-node-add",
                project_name,
                "第3幕-点火升空",
                "--description",
                "发射现场素材",
                "--json",
            )
            payload = _load_json(result)
            assert payload["ok"] is True
            node_id = payload["data"]["node_id"]
            assert payload["data"]["title"] == "第3幕-点火升空"

            result = _run_cli(tmp, "story-node-list", project_name, "--json")
            payload = _load_json(result)
            assert payload["ok"] is True
            assert payload["data"]["nodes"] == [
                {
                    "node_id": node_id,
                    "title": "第3幕-点火升空",
                    "description": "发射现场素材",
                    "search_terms": [],
                    "candidate_urls": [],
                }
            ]
    finally:
        _cleanup_project(project_name)


def test_story_node_attach_via_candidate_add():
    project_name = _unique_project("cli-story-attach")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _setup_temp_workspace(tmp)
            assert _load_json(_run_cli(tmp, "project-create", project_name, "--json"))["ok"]
            assert _load_json(_run_cli(tmp, "story-node-add", project_name, "节点A", "--json"))[
                "ok"
            ]

            # probe 在无工具 workspace 失败；override 接受并仍应关联 story node
            result = _run_cli(
                tmp,
                "candidate-add",
                project_name,
                "https://example.com/video1",
                "--node-title",
                "节点A",
                "--override",
                "--json",
            )
            payload = _load_json(result)
            assert payload["ok"] is True
            assert payload["data"]["state"] == "ACCEPTED"

            # find_project_root 优先命中 REPO_ROOT（__file__ 向上），CLI 项目实际写在
            # REPO_ROOT/output/ 下（与 _cleanup_project 一致）
            project_path = REPO_ROOT / "output" / project_name / "project.json"
            data = json.loads(project_path.read_text(encoding="utf-8"))
            nodes = data.get("story_nodes", [])
            assert any(
                n["title"] == "节点A"
                and "https://example.com/video1" in n.get("candidate_urls", [])
                for n in nodes
            )
            candidates = data.get("candidates", [])
            assert candidates and candidates[0]["story_node_title"] == "节点A"
            assert candidates[0]["state"] == "ACCEPTED"
    finally:
        _cleanup_project(project_name)


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


def test_candidate_add_probe_failure_holds_candidate():
    project_name = _unique_project("cli-probe-fail")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _setup_temp_workspace(tmp)
            _run_cli(tmp, "project-create", project_name, "--json")

            result = _run_cli(
                tmp, "candidate-add", project_name, "https://example.com/video", "--json"
            )
            payload = _load_json(result)
            assert payload["ok"] is False
            assert payload["status"] == "FAILED_PROBE"
            assert payload["data"]["state"] == "FAILED_PROBE"

            result = _run_cli(tmp, "process", project_name, "--json")
            payload = _load_json(result)
            assert payload["data"]["processed"] == 0
    finally:
        _cleanup_project(project_name)


def test_candidate_add_and_process_flow():
    project_name = _unique_project("cli-flow")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _setup_temp_workspace(tmp)
            _run_cli(tmp, "project-create", project_name, "--json")

            result = _run_cli(
                tmp,
                "candidate-add",
                project_name,
                "https://example.com/video",
                "--override",
                "--json",
            )
            payload = _load_json(result)
            assert payload["ok"] is True
            assert payload["status"] == "ACCEPTED"

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
                "--override",
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
