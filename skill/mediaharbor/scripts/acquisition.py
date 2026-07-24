from __future__ import annotations

from datetime import datetime, timezone

from process_runner import sanitize_url
from project import (
    DownloadTask,
    MaterialInfo,
    Project,
    StoryNode,
    _validate_transition,
    load_project,
    save_project,
)


def add_candidate(project_name: str, url: str, node_title: str = "") -> Project | None:
    project = load_project(project_name)
    if project is None:
        return None
    display_url = sanitize_url(url)
    existing = [t for t in project.tasks if t.url == display_url]
    if existing:
        return project
    if node_title:
        for node in project.story_nodes:
            if node.title == node_title:
                if display_url not in node.candidate_urls:
                    node.candidate_urls.append(display_url)
                break
    task = DownloadTask(url=display_url, status="PENDING")
    project.tasks.append(task)
    save_project(project)
    return project


def add_story_node(project_name: str, title: str, description: str) -> Project | None:
    project = load_project(project_name)
    if project is None:
        return None
    node = StoryNode(title=title, description=description)
    project.story_nodes.append(node)
    save_project(project)
    return project


def start_task(project_name: str, url: str) -> DownloadTask | None:
    project = load_project(project_name)
    if project is None:
        return None
    for task in project.tasks:
        if task.url == url and task.status == "PENDING":
            _validate_transition(task.status, "RUNNING", task.task_id)
            task.status = "RUNNING"
            task.started_at = datetime.now(timezone.utc).isoformat()
            save_project(project)
            return task
    return None


def complete_task(
    project_name: str,
    url: str,
    backend: str,
    output_paths: list[str],
    file_hash: str | None = None,
    format: str | None = None,
    duration: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> DownloadTask | None:
    if not output_paths:
        raise ValueError("output_paths must not be empty")
    project = load_project(project_name)
    if project is None:
        return None
    found = False
    for task in project.tasks:
        if task.url == url:
            found = True
            if task.status == "COMPLETED":
                return task
            _validate_transition(task.status, "COMPLETED", task.task_id)
            task.status = "COMPLETED"
            task.backend = backend
            task.output_paths = list(output_paths)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            break
    if not found:
        return None
    display_url = sanitize_url(url)
    for path in output_paths:
        material = MaterialInfo(
            source_url=display_url,
            local_path=path,
            file_hash=file_hash,
            format=format,
            duration=duration,
            width=width,
            height=height,
            verified=True,
        )
        project.materials.append(material)
    save_project(project)
    return next((t for t in project.tasks if t.url == url), None)


def fail_task(project_name: str, url: str, error: str) -> DownloadTask | None:
    project = load_project(project_name)
    if project is None:
        return None
    for task in project.tasks:
        if task.url == url:
            _validate_transition(task.status, "FAILED", task.task_id)
            task.status = "FAILED"
            task.error = error
            task.completed_at = datetime.now(timezone.utc).isoformat()
            save_project(project)
            return task
    return None


def skip_task(project_name: str, url: str) -> DownloadTask | None:
    project = load_project(project_name)
    if project is None:
        return None
    for task in project.tasks:
        if task.url == url and task.status == "PENDING":
            task.status = "SKIPPED"
            task.completed_at = datetime.now(timezone.utc).isoformat()
            save_project(project)
            return task
    return None


def retry_task(project_name: str, url: str) -> DownloadTask | None:
    project = load_project(project_name)
    if project is None:
        return None
    for task in project.tasks:
        if task.url == url and task.status == "FAILED":
            _validate_transition(task.status, "PENDING", task.task_id)
            task.status = "PENDING"
            task.error = None
            task.started_at = None
            task.completed_at = None
            save_project(project)
            return task
    return None


def get_pending_tasks(project_name: str) -> list[DownloadTask]:
    project = load_project(project_name)
    if project is None:
        return []
    return [t for t in project.tasks if t.status == "PENDING"]
