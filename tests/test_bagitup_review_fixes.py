from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parent.parent / "skill" / "bagitup" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_python_module_command_uses_current_interpreter(monkeypatch):
    common = importlib.import_module("_common")
    registry = common.ToolRegistry(
        schema_version=1,
        tools={
            "streamlink": common.ToolEntry(
                roles=["live"],
                kind="python-module",
                module="streamlink",
            )
        },
    )
    monkeypatch.setattr(common.importlib.util, "find_spec", lambda name: object())
    command = common.resolve_registered_command("streamlink", registry=registry)
    assert command == [sys.executable, "-m", "streamlink"]


def test_check_tools_and_runtime_share_resolution(monkeypatch):
    common = importlib.import_module("_common")
    registry = common.ToolRegistry(
        schema_version=1,
        tools={
            "gallery-dl": common.ToolEntry(
                roles=["social"],
                kind="python-module",
                module="gallery_dl",
                required=True,
            )
        },
    )
    monkeypatch.setattr(common.importlib.util, "find_spec", lambda name: None)
    result = common.check_tools(registry)
    assert result.status == "DEGRADED"
    assert result.tools["gallery-dl"].exists is False
    assert common.resolve_registered_command("gallery-dl", registry=registry) is None


def test_add_candidate_refreshes_expiring_execution_url(tmp_path, monkeypatch):
    project_mod = importlib.import_module("project")
    acquisition = importlib.import_module("acquisition")
    monkeypatch.setattr(project_mod, "ensure_output_dir", lambda start=None: tmp_path)

    name = "signed-url-refresh"
    project_mod.save_project(project_mod.create_project(name))
    old = "https://example.com/video?signature=old&expires=1"
    new = "https://example.com/video?signature=new&expires=2"
    acquisition.add_candidate(name, old)
    acquisition.add_candidate(name, new)

    project = project_mod.load_project(name)
    assert project is not None
    assert len(project.tasks) == 1
    assert project.tasks[0].execution_url == new
    assert "signature=old" not in project.tasks[0].url
    assert "signature=new" not in project.tasks[0].url


def test_state_transition_error_is_not_false_success(monkeypatch):
    orchestrator = importlib.import_module("orchestrator")
    task = SimpleNamespace(
        url="https://example.com/video",
        execution_url="https://example.com/video",
        status="PENDING",
        task_id="task-1",
        output_paths=[],
    )
    monkeypatch.setattr(orchestrator, "_recover_source_transactions", lambda _name: 0)
    monkeypatch.setattr(orchestrator, "recover_interrupted_tasks", lambda _name: 0)
    monkeypatch.setattr(orchestrator, "get_pending_tasks", lambda _name: [task])
    monkeypatch.setattr(orchestrator, "start_task", lambda _name, _url: task)
    monkeypatch.setattr(
        orchestrator,
        "_process_started_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        orchestrator,
        "fail_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad transition")),
    )
    monkeypatch.setattr(
        orchestrator,
        "load_project",
        lambda _name: SimpleNamespace(
            tasks=[SimpleNamespace(url=task.url, status="RUNNING", output_paths=[])]
        ),
    )
    monkeypatch.setattr(orchestrator, "save_report", lambda _name: None)
    monkeypatch.setattr(orchestrator, "save_handoff", lambda _name: None)

    result = orchestrator.process_pending("demo")
    assert result["success"] == 0
    assert result["failed"] == 1
    assert result["details"][0]["status"] == "INTERNAL_ERROR"
