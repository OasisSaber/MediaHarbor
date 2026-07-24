from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from _common import ensure_output_dir
from acquisition import complete_task, fail_task, get_pending_tasks, start_task
from ffprobe_validator import get_media_info, parse_ffprobe_output, resolve_ffprobe
from process_runner import SUCCESS, ProcessResult, ProcessRunner, sanitize_url
from project import load_project
from report import save_handoff, save_report
from router import download_with_fallback
from safe_path import resolve_project_dir


def _sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _generate_source_json(
    project_name: str, url: str, file_path: Path, backend: str, attempts: list
) -> Path | None:
    project = load_project(project_name)
    if project is None:
        return None
    display_url = sanitize_url(url)
    entry = {
        "schema_version": 1,
        "source_id": f"{project.project_id}-{len(project.materials):03d}",
        "project_id": project.project_id,
        "story_node_id": None,
        "display_url": display_url,
        "platform": None,
        "platform_media_id": None,
        "title": None,
        "uploader": None,
        "publish_date": None,
        "duration": None,
        "selected_backend": backend,
        "attempt_history": [],
        "local_files": [str(file_path)],
        "subtitles": [],
        "thumbnail": None,
        "sha256": None,
        "ffprobe_result": None,
        "acquisition_timestamp": datetime.now(timezone.utc).isoformat(),
        "rights_access_note": "Verify copyright before use.",
        "final_status": "SUCCESS",
    }
    if attempts:
        for a in attempts:
            entry["attempt_history"].append(
                {
                    "backend": a.get("backend"),
                    "status": a.get("status"),
                    "error": a.get("safe_error", "")[:200],
                }
            )
    entry["sha256"] = _sha256(file_path)
    ffprobe = resolve_ffprobe()
    if ffprobe and file_path.is_file():
        from ffprobe_validator import validate_media

        result = validate_media(file_path)
        if result.status == SUCCESS:
            info = parse_ffprobe_output(result.stdout)
            if info:
                media = get_media_info(info)
                entry["ffprobe_result"] = media
                entry["duration"] = media.get("duration")

    root = ensure_output_dir()
    pdir = resolve_project_dir(root, project_name) / "acquisition" / "sources"
    pdir.mkdir(parents=True, exist_ok=True)
    spath = pdir / f"{entry['source_id']}.json"
    spath.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    return spath


def _validate_downloaded_file(file_path: Path, output_dir: Path) -> ProcessResult:
    if not file_path.is_file() or file_path.stat().st_size == 0:
        return ProcessResult(
            returncode=-1, stdout="", stderr="File missing or empty", status="VALIDATION_FAILED"
        )
    try:
        file_path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        return ProcessResult(
            returncode=-1, stdout="", stderr="File outside output dir", status="VALIDATION_FAILED"
        )
    from ffprobe_validator import get_media_info, parse_ffprobe_output, validate_media

    probe = validate_media(file_path)
    if probe.status != SUCCESS:
        return probe
    info = parse_ffprobe_output(probe.stdout)
    if not info:
        return ProcessResult(
            returncode=-1, stdout="", stderr="ffprobe parse failed", status="VALIDATION_FAILED"
        )
    media = get_media_info(info)
    if media["duration"] <= 0:
        return ProcessResult(
            returncode=-1, stdout="", stderr="Invalid duration", status="VALIDATION_FAILED"
        )
    if not media["has_video"]:
        return ProcessResult(
            returncode=-1, stdout="", stderr="No video stream", status="VALIDATION_FAILED"
        )
    return ProcessResult(returncode=0, stdout="validated", stderr="", status=SUCCESS)


def process_pending(project_name: str, runner: ProcessRunner | None = None) -> dict:
    if runner is None:
        runner = ProcessRunner(timeout=600, max_retries=2)
    pending = get_pending_tasks(project_name)
    results = {"processed": 0, "success": 0, "failed": 0, "details": []}

    for task in pending:
        if "REDACTED" in task.url:
            fail_task(
                project_name,
                task.url,
                "Cannot download: URL was sanitized (REDACTED). Raw URL must be re-provided.",
            )
            results["failed"] += 1
            results["details"].append({"url": task.url, "error": "URL sanitized"})
            continue

        started = start_task(project_name, task.url)
        if started is None:
            continue
        results["processed"] += 1

        root = ensure_output_dir()
        output_dir = resolve_project_dir(root, project_name) / "assets" / "originals"
        output_dir.mkdir(parents=True, exist_ok=True)

        result, backend = download_with_fallback(task.url, output_dir, runner=runner)
        entry = {"url": task.url, "backend": backend, "status": result.status}

        if result.status == SUCCESS and result.stdout.strip():
            file_path = Path(result.stdout.strip().splitlines()[-1])
            validation = _validate_downloaded_file(file_path, output_dir)
            if validation.status == SUCCESS:
                try:
                    source_path = _generate_source_json(
                        project_name,
                        task.url,
                        file_path,
                        backend or "",
                        [a.__dict__ for a in result.attempts],
                    )
                    if source_path is None:
                        raise RuntimeError("Failed to generate source.json: project not found")
                    source_data = json.loads(source_path.read_text(encoding="utf-8"))
                    media = source_data.get("ffprobe_result") or {}
                    complete_task(
                        project_name,
                        task.url,
                        backend or "unknown",
                        [str(file_path)],
                        file_hash=source_data.get("sha256"),
                        format=media.get("format_name"),
                        duration=media.get("duration"),
                        width=media.get("width"),
                        height=media.get("height"),
                    )
                    results["success"] += 1
                    entry["file"] = str(file_path)
                except Exception as e:
                    fail_task(project_name, task.url, f"source_json/complete: {e!s}")
                    results["failed"] += 1
                    entry["error"] = str(e)[:200]
            else:
                fail_task(project_name, task.url, f"Validation: {validation.stderr[:200]}")
                results["failed"] += 1
                entry["error"] = validation.stderr[:200]
        else:
            fail_task(project_name, task.url, f"{result.status}: {result.stderr[:200]}")
            results["failed"] += 1
            entry["error"] = result.stderr[:200]
        results["details"].append(entry)

    save_report(project_name)
    save_handoff(project_name)
    return results
