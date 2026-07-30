from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from _common import ensure_output_dir
from acquisition import (
    complete_task,
    fail_task,
    get_pending_tasks,
    recover_interrupted_tasks,
    start_task,
)
from ffprobe_validator import (
    get_media_info,
    parse_ffprobe_output,
    resolve_ffprobe,
    validate_downloaded_file,
)
from process_runner import (
    SUCCESS,
    BackendResult,
    ProcessResult,
    ProcessRunner,
    sanitize_stderr,
    sanitize_url,
)
from project import DownloadTask, _atomic_write, load_project
from report import save_handoff, save_report
from router import download_with_fallback
from safe_path import resolve_project_dir


def _sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_source_entry(
    project_name: str,
    url: str,
    result: BackendResult,
    backend: str,
    main_file: Path | None = None,
) -> dict | None:
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

    return entry


def _source_dir(project_name: str) -> Path:
    root = ensure_output_dir()
    path = resolve_project_dir(root, project_name) / "acquisition" / "sources"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_source_entry(project_name: str, entry: dict) -> Path:
    path = _source_dir(project_name) / f"{entry['source_id']}.json"
    _atomic_write(path, json.dumps(entry, indent=2, ensure_ascii=False))
    return path


def _generate_source_json(
    project_name: str,
    url: str,
    result: BackendResult,
    backend: str,
    main_file: Path | None = None,
) -> Path | None:
    entry = _build_source_entry(project_name, url, result, backend, main_file)
    if entry is None:
        return None
    return _write_source_entry(project_name, entry)


def _stage_source_transaction(
    project_name: str,
    task_id: str,
    entry: dict,
    artifacts: list[Path],
) -> Path:
    pending = _source_dir(project_name) / f"{task_id}.source.pending"
    transaction = {
        "task_id": task_id,
        "target": f"{entry['source_id']}.json",
        "artifacts": [str(path) for path in artifacts],
        "source": entry,
    }
    _atomic_write(pending, json.dumps(transaction, indent=2, ensure_ascii=False))
    return pending


def _read_source_transaction(pending: Path) -> dict:
    transaction = json.loads(pending.read_text(encoding="utf-8"))
    target = transaction.get("target")
    if (
        not isinstance(target, str)
        or Path(target).name != target
        or not target.endswith(".json")
        or not isinstance(transaction.get("source"), dict)
    ):
        raise ValueError("Invalid source transaction")
    return transaction


def _remove_pending_file(pending: Path) -> None:
    pending.unlink(missing_ok=True)
    pending.with_suffix(pending.suffix + ".bak").unlink(missing_ok=True)
    pending.with_suffix(pending.suffix + ".tmp").unlink(missing_ok=True)


def _commit_source_transaction(pending: Path) -> Path:
    transaction = _read_source_transaction(pending)
    target = pending.parent / transaction["target"]
    _atomic_write(
        target,
        json.dumps(transaction["source"], indent=2, ensure_ascii=False),
    )
    _remove_pending_file(pending)
    return target


def _remove_transaction_artifacts(project_name: str, transaction: dict) -> None:
    root = ensure_output_dir()
    originals = (resolve_project_dir(root, project_name) / "assets" / "originals").resolve()
    for raw_path in transaction.get("artifacts", []):
        try:
            artifact = Path(raw_path).resolve()
            artifact.relative_to(originals)
            artifact.unlink(missing_ok=True)
        except (OSError, TypeError, ValueError):
            continue


def _recover_source_transactions(project_name: str) -> int:
    project = load_project(project_name)
    if project is None:
        return 0
    tasks = {task.task_id: task for task in project.tasks}
    recovered = 0
    for pending in _source_dir(project_name).glob("*.source.pending"):
        try:
            transaction = _read_source_transaction(pending)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            _remove_pending_file(pending)
            continue
        task = tasks.get(transaction.get("task_id"))
        if task is not None and task.status == "COMPLETED":
            try:
                _commit_source_transaction(pending)
                recovered += 1
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                continue
        else:
            _remove_transaction_artifacts(project_name, transaction)
            _remove_pending_file(pending)
    return recovered


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


def _fail_started_task(
    project_name: str,
    url: str,
    entry: dict,
    error: str,
) -> tuple[bool, dict]:
    safe_error = sanitize_stderr(error)[:200]
    fail_task(project_name, url, safe_error)
    entry["error"] = safe_error
    return False, entry


def _process_started_task(
    project_name: str,
    task: DownloadTask,
    runner: ProcessRunner,
) -> tuple[bool, dict]:
    root = ensure_output_dir()
    project_dir = resolve_project_dir(root, project_name)
    final_dir = project_dir / "assets" / "originals"
    staging_dir = _prepare_task_staging(project_dir, task.task_id)
    finalized_paths: list[Path] = []
    source_pending: Path | None = None
    project_committed = False

    try:
        result, backend = download_with_fallback(task.url, staging_dir, runner=runner)
        entry = {"url": task.url, "backend": backend, "status": result.status}
        if result.status != SUCCESS:
            return _fail_started_task(
                project_name,
                task.url,
                entry,
                f"{result.status}: {result.stderr}",
            )
        if not result.output_paths:
            return _fail_started_task(
                project_name,
                task.url,
                entry,
                "VALIDATION_FAILED: no output files",
            )

        media_types = result.metadata.get("media_types", {})
        main_candidates = [Path(path) for path in media_types.get("main", [])] or list(
            result.output_paths
        )
        validations: list[ProcessResult] = []
        for file_path in main_candidates:
            validation = _validate_downloaded_file(file_path, staging_dir)
            if validation.status != SUCCESS:
                break
            validations.append(validation)
        if len(validations) != len(main_candidates):
            return _fail_started_task(
                project_name,
                task.url,
                entry,
                "VALIDATION_FAILED: invalid media",
            )

        result, finalized_main = _finalize_artifacts(
            result,
            staging_dir,
            final_dir,
            task.task_id,
        )
        finalized_paths = list(result.output_paths)
        valid_file = finalized_main[0]
        source_entry = _build_source_entry(
            project_name,
            task.url,
            result,
            backend or "",
            main_file=valid_file,
        )
        if source_entry is None:
            raise RuntimeError("Failed to generate source.json: project not found")
        source_pending = _stage_source_transaction(
            project_name,
            task.task_id,
            source_entry,
            finalized_paths,
        )
        media = source_entry.get("ffprobe_result") or {}
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
        completed = complete_task(
            project_name,
            task.url,
            backend or "unknown",
            [str(path) for path in result.output_paths],
            material_paths=[str(path) for path in finalized_main],
            material_hashes={str(path): _sha256(path) for path in finalized_main},
            **media_fields,
        )
        if completed is None:
            raise RuntimeError("Failed to complete task: project or task not found")
        project_committed = True
        try:
            _commit_source_transaction(source_pending)
        except OSError:
            entry["source_pending"] = True
        entry["file"] = str(valid_file)
        return True, entry
    except Exception:
        if not project_committed:
            if source_pending is not None:
                _remove_pending_file(source_pending)
            for path in finalized_paths:
                path.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def process_pending(project_name: str, runner: ProcessRunner | None = None) -> dict:
    if runner is None:
        runner = ProcessRunner(timeout=600, max_retries=2)
    source_transactions_recovered = _recover_source_transactions(project_name)
    recovered = recover_interrupted_tasks(project_name)
    pending = get_pending_tasks(project_name)
    results = {
        "processed": 0,
        "success": 0,
        "failed": 0,
        "recovered": recovered,
        "source_transactions_recovered": source_transactions_recovered,
        "details": [],
    }

    for task in pending:
        if "REDACTED" in task.url:
            started = start_task(project_name, task.url)
            if started is None:
                continue
            results["processed"] += 1
            _, entry = _fail_started_task(
                project_name,
                task.url,
                {"url": task.url, "backend": None, "status": "VALIDATION_FAILED"},
                "Cannot download a sanitized URL without its raw runtime value",
            )
            results["failed"] += 1
            results["details"].append(entry)
            continue

        started = start_task(project_name, task.url)
        if started is None:
            continue
        results["processed"] += 1
        try:
            succeeded, entry = _process_started_task(project_name, started, runner)
        except Exception as error:
            safe_error = sanitize_stderr(f"{type(error).__name__}: {error}")[:200]
            fail_task(project_name, task.url, f"INTERNAL_ERROR: {safe_error}")
            succeeded = False
            entry = {
                "url": task.url,
                "backend": None,
                "status": "INTERNAL_ERROR",
                "error": safe_error,
            }
        results["success" if succeeded else "failed"] += 1
        results["details"].append(entry)

    save_report(project_name)
    save_handoff(project_name)
    return results
