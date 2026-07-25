from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import ensure_output_dir
from safe_path import resolve_project_dir, validate_project_name

SCHEMA_VERSION = 1

VALID_STATUSES = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"}
ALLOWED_TRANSITIONS = {
    "PENDING": {"RUNNING", "SKIPPED"},
    "RUNNING": {"COMPLETED", "FAILED", "PENDING"},
    "FAILED": {"PENDING"},
    "COMPLETED": set(),
    "SKIPPED": {"PENDING"},
}


@dataclass
class StoryNode:
    node_id: str = ""
    title: str = ""
    description: str = ""
    search_terms: list[str] = field(default_factory=list)
    candidate_urls: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.node_id:
            self.node_id = str(uuid.uuid4())[:8]


@dataclass
class DownloadTask:
    url: str
    task_id: str = ""
    status: str = "PENDING"
    backend: str | None = None
    output_paths: list[str] = field(default_factory=list)
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def __post_init__(self):
        if not self.task_id:
            self.task_id = str(uuid.uuid4())[:8]


@dataclass
class MaterialInfo:
    source_url: str
    local_path: str
    file_hash: str | None = None
    format: str | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    verified: bool = False


@dataclass
class Project:
    name: str
    schema_version: int = SCHEMA_VERSION
    project_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    script: str = ""
    story_nodes: list[StoryNode] = field(default_factory=list)
    tasks: list[DownloadTask] = field(default_factory=list)
    materials: list[MaterialInfo] = field(default_factory=list)

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.project_id:
            self.project_id = str(uuid.uuid4())[:12]
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


def create_project(name: str, script: str = "") -> Project:
    validate_project_name(name)
    return Project(name=name, script=script)


def _project_subdirs(name: str) -> list[str]:
    return ["input", "planning", "acquisition", "assets/originals", "logs", "reports"]


def project_dir(name: str) -> Path:
    base = ensure_output_dir()
    return resolve_project_dir(base, name)


def _init_project_dirs(name: str) -> Path:
    pdir = project_dir(name)
    for sub in _project_subdirs(name):
        (pdir / sub).mkdir(parents=True, exist_ok=True)
    return pdir


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    bak = path.with_suffix(path.suffix + ".bak")
    tmp.write_text(content, encoding="utf-8")
    main_existed = path.is_file()
    if main_existed:
        try:
            os.replace(path, bak)
        except OSError:
            _safe_unlink(tmp)
            raise
    try:
        os.replace(tmp, path)
    except OSError:
        if main_existed:
            try:
                os.replace(bak, path)
            except OSError:
                pass
        _safe_unlink(tmp)
        raise


def save_project(project: Project) -> Path:
    pdir = _init_project_dirs(project.name)
    project.updated_at = datetime.now(timezone.utc).isoformat()
    data = asdict(project)
    data["schema_version"] = project.schema_version
    path = pdir / "project.json"
    _atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False))
    return path


def _read_project_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_project(name: str) -> Project | None:
    pdir = project_dir(name)
    path = pdir / "project.json"
    data = _read_project_json(path)
    if data is None:
        bak = path.with_suffix(path.suffix + ".bak")
        data = _read_project_json(bak)
    if data is None:
        return None
    return _project_from_dict(data)


def recover_stale_running(project_name: str) -> int:
    project = load_project(project_name)
    if project is None:
        return 0
    count = 0
    for task in project.tasks:
        if task.status == "RUNNING":
            _validate_transition(task.status, "PENDING", task.task_id)
            task.status = "PENDING"
            task.started_at = None
            task.error = None
            count += 1
    if count:
        save_project(project)
    return count


def _validate_transition(current: str, next_state: str, task_id: str):
    if next_state not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {next_state}")
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if next_state not in allowed:
        raise ValueError(f"Invalid transition {current} -> {next_state} for task {task_id}")


def _project_from_dict(data: dict[str, Any]) -> Project:
    nodes = [StoryNode(**n) for n in data.get("story_nodes", [])]
    tasks = [DownloadTask(**t) for t in data.get("tasks", [])]
    materials = [MaterialInfo(**m) for m in data.get("materials", [])]
    return Project(
        name=data["name"],
        schema_version=data.get("schema_version", 1),
        project_id=data.get("project_id", ""),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        script=data.get("script", ""),
        story_nodes=nodes,
        tasks=tasks,
        materials=materials,
    )
