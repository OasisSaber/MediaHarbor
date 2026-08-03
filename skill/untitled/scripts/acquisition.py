from __future__ import annotations

from datetime import datetime, timezone

from process_runner import ProcessRunner, sanitize_url
from project import (
    Candidate,
    DownloadTask,
    MaterialInfo,
    Project,
    StoryNode,
    _validate_transition,
    load_project,
    save_project,
)

_REFRESHABLE_TASK_STATES = {"PENDING", "FAILED", "SKIPPED"}


def _refresh_execution_url(project: Project, display_url: str, execution_url: str) -> bool:
    """Refresh a secret-bearing URL without duplicating the sanitized task identity."""
    changed = False
    for task in project.tasks:
        if task.url != display_url or task.status not in _REFRESHABLE_TASK_STATES:
            continue
        if task.execution_url != execution_url:
            task.execution_url = execution_url
            changed = True
    for candidate in project.candidates:
        if candidate.display_url == display_url and candidate.execution_url != execution_url:
            candidate.execution_url = execution_url
            changed = True
    return changed


def add_candidate(project_name: str, url: str, node_title: str = "") -> Project | None:
    project = load_project(project_name)
    if project is None:
        return None
    display_url = sanitize_url(url)
    existing = [task for task in project.tasks if task.url == display_url]
    if existing:
        if _refresh_execution_url(project, display_url, url):
            save_project(project)
        return project
    if node_title:
        for node in project.story_nodes:
            if node.title == node_title:
                if display_url not in node.candidate_urls:
                    node.candidate_urls.append(display_url)
                break
    task = DownloadTask(url=display_url, execution_url=url, status="PENDING")
    project.tasks.append(task)
    save_project(project)
    return project


def _attach_story_node(project: Project, candidate: Candidate) -> None:
    if not candidate.story_node_title:
        return
    for node in project.story_nodes:
        if node.title == candidate.story_node_title:
            if candidate.display_url not in node.candidate_urls:
                node.candidate_urls.append(candidate.display_url)
            break


def _enqueue_candidate(project: Project, candidate: Candidate) -> None:
    if candidate.candidate_id not in [c.candidate_id for c in project.candidates]:
        project.candidates.append(candidate)
    task = DownloadTask(
        url=candidate.display_url,
        execution_url=candidate.execution_url,
        status="PENDING",
    )
    project.tasks.append(task)
    _attach_story_node(project, candidate)
    save_project(project)


def preflight_candidate(
    project_name: str,
    url: str,
    search_query: str = "",
    node_title: str = "",
    override: bool = False,
    runner: ProcessRunner | None = None,
) -> Candidate | None:
    """Probe a candidate, score provenance, and enqueue only when accepted.

    Probe failures produce an explicit ``FAILED_PROBE`` state with a reason,
    never a fabricated high score. Candidates below the provenance threshold
    remain recorded with rejection reasons and are not downloaded unless an
    explicit override is supplied.
    """
    from provenance import MIN_PROVENANCE_THRESHOLD, reasons_to_messages, score_candidate
    from ytdlp_adapter import parse_probe_json, probe_url

    project = load_project(project_name)
    if project is None:
        return None

    display_url = sanitize_url(url)
    for existing in project.candidates:
        if existing.display_url == display_url:
            changed = _refresh_execution_url(project, display_url, url)
            if existing.execution_url != url:
                existing.execution_url = url
                changed = True
            if changed:
                save_project(project)
            return existing

    candidate = Candidate(
        execution_url=url,
        display_url=display_url,
        search_query=search_query or None,
        story_node_title=node_title or None,
    )
    probe = probe_url(url, runner=runner)
    if probe.status != "SUCCESS":
        candidate.state = "FAILED_PROBE"
        candidate.probe_error = sanitize_url(probe.stderr)[:200]
        candidate.rejection_reasons.append("probe-failed")
        if override:
            candidate.overridden = True
            candidate.state = "ACCEPTED"
            _enqueue_candidate(project, candidate)
        else:
            project.candidates.append(candidate)
            save_project(project)
        return candidate

    info = parse_probe_json(probe.stdout) or {}
    candidate.platform = info.get("extractor")
    candidate.platform_media_id = info.get("id")
    candidate.title = info.get("title")
    candidate.uploader = info.get("uploader") or info.get("channel")
    candidate.uploader_id = info.get("uploader_id") or info.get("channel_id")
    candidate.publish_date = info.get("upload_date") or info.get("release_date")
    candidate.duration = info.get("duration")
    candidate.is_live = bool(
        info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming")
    )
    candidate.format_summary = info.get("formats_summary")

    duplicate = bool(
        candidate.platform_media_id
        and any(
            c.platform_media_id == candidate.platform_media_id
            and c.candidate_id != candidate.candidate_id
            for c in project.candidates
        )
    )
    score, reason_codes = score_candidate(
        candidate.title,
        candidate.uploader,
        candidate.duration,
        candidate.is_live,
        duplicate,
    )
    candidate.provenance_score = score
    candidate.provenance_reasons = reasons_to_messages(reason_codes)

    if override:
        candidate.overridden = True
        candidate.state = "ACCEPTED"
        _enqueue_candidate(project, candidate)
    elif duplicate:
        candidate.state = "REJECTED"
        candidate.rejection_reasons.append("duplicate-platform-media-id")
        project.candidates.append(candidate)
        save_project(project)
    elif score >= MIN_PROVENANCE_THRESHOLD:
        candidate.state = "ACCEPTED"
        _enqueue_candidate(project, candidate)
    else:
        candidate.state = "REJECTED"
        candidate.rejection_reasons.append("below-provenance-threshold")
        project.candidates.append(candidate)
        save_project(project)
    return candidate


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
    material_paths: list[str] | None = None,
    material_hashes: dict[str, str] | None = None,
    file_hash: str | None = None,
    format: str | None = None,
    duration: float | None = None,
    width: int | None = None,
    height: int | None = None,
    quality_status: str | None = None,
    quality_reasons: list[str] | None = None,
    editorial_status: str | None = None,
    editorial_reasons: list[str] | None = None,
    visual_analysis: dict | None = None,
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
    assessment_time = datetime.now(timezone.utc).isoformat()
    for path in material_paths if material_paths is not None else output_paths:
        material = MaterialInfo(
            source_url=display_url,
            local_path=path,
            file_hash=(material_hashes or {}).get(path, file_hash),
            format=format,
            duration=duration,
            width=width,
            height=height,
            verified=True,
            technical_status="PASS",
            quality_status=quality_status or "UNKNOWN",
            editorial_status=editorial_status or "UNREVIEWED",
            quality_reasons=list(quality_reasons) if quality_reasons else [],
            editorial_reasons=list(editorial_reasons) if editorial_reasons else [],
            visual_analysis=visual_analysis,
            assessment_timestamp=assessment_time,
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


def recover_interrupted_tasks(project_name: str) -> int:
    project = load_project(project_name)
    if project is None:
        return 0
    recovered = 0
    completed_at = datetime.now(timezone.utc).isoformat()
    for task in project.tasks:
        if task.status != "RUNNING":
            continue
        _validate_transition(task.status, "FAILED", task.task_id)
        task.status = "FAILED"
        task.error = "Interrupted before task completion"
        task.completed_at = completed_at
        recovered += 1
    if recovered:
        save_project(project)
    return recovered
