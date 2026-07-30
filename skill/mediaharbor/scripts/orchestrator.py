from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from _common import ensure_output_dir
from acquisition import complete_task, fail_task, get_pending_tasks, start_task
from ffprobe_validator import (
    get_media_info,
    parse_ffprobe_output,
    resolve_ffprobe,
    validate_downloaded_file,
)
from process_runner import SUCCESS, BackendResult, ProcessResult, ProcessRunner, sanitize_url
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
    project_name: str,
    url: str,
    result: BackendResult,
    backend: str,
    main_file: Path | None = None,
) -> Path | None:
    project = load_project(project_name)
    if project is None:
        return None

    primary = main_file or (result.output_paths[0] if result.output_paths else None)
    if primary is None:
        return None

    media_types = result.metadata.get("media_types", {})
    local_files = media_types.get("main") or [str(p) for p in result.output_paths]
    subtitles = media_types.get("subtitle", [])
    thumbnails = media_types.get("thumbnail", [])
    thumbnail = thumbnails[0] if thumbnails else None

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
        "local_files": local_files,
        "subtitles": subtitles,
        "thumbnail": thumbnail,
        "sha256": None,
        "ffprobe_result": None,
        "acquisition_timestamp": datetime.now(timezone.utc).isoformat(),
        "rights_access_note": "Verify copyright before use.",
        "final_status": "SUCCESS",
    }
    if result.attempts:
        for a in result.attempts:
            entry["attempt_history"].append(
                {
                    "backend": a.backend,
                    "status": a.status,
                    "error": a.safe_error[:200],
                }
            )
    entry["sha256"] = _sha256(primary)
    ffprobe = resolve_ffprobe()
    if ffprobe and primary.is_file():
        from ffprobe_validator import validate_media

        p_result = validate_media(primary)
        if p_result.status == SUCCESS:
            info = parse_ffprobe_output(p_result.stdout)
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
    return validate_downloaded_file(file_path, output_dir)


def _prepare_task_staging(project_dir: Path, task_id: str) -> Path:
    staging_root = (project_dir / "assets" / ".staging").resolve()
    task_dir = (staging_root / task_id).resolve()
    task_dir.relative_to(staging_root)
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def _final_destination(final_dir: Path, task_id: str, source: Path) -> Path:
    destination = final_dir / f"{task_id}-{source.name}"
    counter = 2
    while destination.exists():
        destination = final_dir / f"{task_id}-{counter}-{source.name}"
        counter += 1
    return destination


def _finalize_artifacts(
    result: BackendResult,
    staging_dir: Path,
    final_dir: Path,
    task_id: str,
) -> tuple[BackendResult, list[Path]]:
    staging_root = staging_dir.resolve()
    final_dir.mkdir(parents=True, exist_ok=True)
    moved: dict[Path, Path] = {}
    for source in result.output_paths:
        resolved = source.resolve()
        resolved.relative_to(staging_root)
        destination = _final_destination(final_dir, task_id, source)
        shutil.move(str(source), str(destination))
        moved[resolved] = destination

    result.output_paths = [moved[path.resolve()] for path in result.output_paths]
    media_types = result.metadata.get("media_types", {})
    for media_type, paths in media_types.items():
        media_types[media_type] = [
            str(moved[Path(path).resolve()]) for path in paths if Path(path).resolve() in moved
        ]
    result.metadata["media_types"] = media_types
    main_paths = [Path(path) for path in media_types.get("main", [])]
    if not main_paths:
        main_paths = list(result.output_paths)
    return result, main_paths


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
        project_dir = resolve_project_dir(root, project_name)
        final_dir = project_dir / "assets" / "originals"
        staging_dir = _prepare_task_staging(project_dir, task.task_id)

        result, backend = download_with_fallback(task.url, staging_dir, runner=runner)
        entry = {"url": task.url, "backend": backend, "status": result.status}

        if result.status == SUCCESS:
            if not result.output_paths:
                fail_task(
                    project_name,
                    task.url,
                    "Backend reported SUCCESS but no output files were discovered",
                )
                results["failed"] += 1
                entry["error"] = "VALIDATION_FAILED: no output files"
                results["details"].append(entry)
                shutil.rmtree(staging_dir, ignore_errors=True)
                continue

            media_types = result.metadata.get("media_types", {})
            main_candidates = [Path(path) for path in media_types.get("main", [])] or list(
                result.output_paths
            )
            validations: list[ProcessResult] = []
            for fp in main_candidates:
                validation = _validate_downloaded_file(fp, staging_dir)
                if validation.status != SUCCESS:
                    break
                validations.append(validation)

            if len(validations) != len(main_candidates):
                fail_task(
                    project_name,
                    task.url,
                    "At least one discovered media file failed validation",
                )
                results["failed"] += 1
                entry["error"] = "VALIDATION_FAILED: invalid media"
                results["details"].append(entry)
                shutil.rmtree(staging_dir, ignore_errors=True)
                continue

            try:
                result, finalized_main = _finalize_artifacts(
                    result,
                    staging_dir,
                    final_dir,
                    task.task_id,
                )
                valid_file = finalized_main[0]
                source_path = _generate_source_json(
                    project_name,
                    task.url,
                    result,
                    backend or "",
                    main_file=valid_file,
                )
                if source_path is None:
                    raise RuntimeError("Failed to generate source.json: project not found")
                source_data = json.loads(source_path.read_text(encoding="utf-8"))
                media = source_data.get("ffprobe_result") or {}
                media_fields = (
                    {
                        "format": media.get("format_name"),
                        "duration": media.get("duration"),
                        "width": media.get("width"),
                        "height": media.get("height"),
                    }
                    if len(finalized_main) == 1
                    else {}
                )
                complete_task(
                    project_name,
                    task.url,
                    backend or "unknown",
                    [str(p) for p in result.output_paths],
                    material_paths=[str(p) for p in finalized_main],
                    material_hashes={str(path): _sha256(path) for path in finalized_main},
                    **media_fields,
                )
                results["success"] += 1
                entry["file"] = str(valid_file)
            except Exception as e:
                fail_task(project_name, task.url, f"source_json/complete: {e!s}")
                results["failed"] += 1
                entry["error"] = str(e)[:200]
        else:
            fail_task(project_name, task.url, f"{result.status}: {result.stderr[:200]}")
            results["failed"] += 1
            entry["error"] = result.stderr[:200]
        results["details"].append(entry)
        shutil.rmtree(staging_dir, ignore_errors=True)

    save_report(project_name)
    save_handoff(project_name)
    return results
