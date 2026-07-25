from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "mediaharbor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Environment setup helpers
# ---------------------------------------------------------------------------

_MOCK_TOOLS = [
    ("yt-dlp", "yt-dlp"),
    ("streamlink", "streamlink"),
    ("yutto", "yutto"),
    ("n-m3u8dl-re", "N_m3u8DL-RE"),
    ("gallery-dl", "gallery-dl"),
    ("ffprobe", "ffmpeg"),
]


def _wrapper_ext() -> str:
    return ".bat"


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _create_tool_wrapper(wrapper_dir: Path, tool_name: str, dispatcher_path: Path) -> Path:
    ext = _wrapper_ext()
    wrapper_path = wrapper_dir / f"{tool_name}{ext}"
    if sys.platform == "win32":
        wrapper_path.write_text(
            f'@echo off\npython "{dispatcher_path}" {tool_name} %*\n',
            encoding="ascii",
        )
    else:
        wrapper_path.write_text(
            f'#!/bin/sh\nexec python3 "{dispatcher_path}" {tool_name} "$@"\n',
            encoding="ascii",
        )
        wrapper_path.chmod(0o755)
    return wrapper_path


def _make_routing_json(target: Path):
    target.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "routes": [
                    {
                        "name": "bilibili",
                        "patterns": ["bilibili\\.com", "b23\\.tv"],
                        "backends": ["yt-dlp", "yutto"],
                        "max_retries": 1,
                        "drm_stop": True,
                    },
                    {
                        "name": "vod",
                        "patterns": ["^https?://"],
                        "backends": ["yt-dlp", "streamlink", "yutto", "n-m3u8dl-re", "gallery-dl"],
                        "max_retries": 1,
                        "drm_stop": True,
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _make_tools_json(target: Path):
    ext = _wrapper_ext()
    target.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tools": {
                    "yt-dlp": {
                        "roles": ["probe", "vod"],
                        "required": True,
                        "platforms": {"windows-x64": f"yt-dlp/yt-dlp{ext}"},
                    },
                    "ffprobe": {
                        "roles": ["validate"],
                        "required": True,
                        "platforms": {"windows-x64": f"ffmpeg/ffprobe{ext}"},
                    },
                    "ffmpeg": {
                        "roles": ["merge"],
                        "required": False,
                        "platforms": {"windows-x64": f"ffmpeg/ffmpeg{ext}"},
                    },
                    "yutto": {
                        "roles": ["bilibili"],
                        "required": False,
                        "platforms": {"windows-x64": f"yutto/yutto{ext}"},
                    },
                    "streamlink": {
                        "roles": ["live"],
                        "required": False,
                        "platforms": {"windows-x64": f"streamlink/streamlink{ext}"},
                    },
                    "n-m3u8dl-re": {
                        "roles": ["hls"],
                        "required": False,
                        "platforms": {"windows-x64": f"N_m3u8DL-RE/N_m3u8DL-RE{ext}"},
                    },
                    "gallery-dl": {
                        "roles": ["social"],
                        "required": False,
                        "platforms": {"windows-x64": f"gallery-dl/gallery-dl{ext}"},
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _setup_environment(tmp_root: Path) -> None:
    _ensure_dir(tmp_root)
    (tmp_root / "AGENT_READ_ME_FIRST.md").write_text("")
    _ensure_dir(tmp_root / "skill" / "mediaharbor")
    (tmp_root / "skill" / "mediaharbor" / "SKILL.md").write_text(
        "---\ntitle: Integration Test\n---\n", encoding="utf-8"
    )
    _ensure_dir(tmp_root / "skill" / "mediaharbor" / "scripts")

    dl_dir = _ensure_dir(tmp_root / "download-tools")

    dispatcher_src = REPO_ROOT / "tests" / "fixtures" / "mock_tools.py"
    dispatcher_dst = dl_dir / "mock_tools.py"
    shutil.copy2(str(dispatcher_src), str(dispatcher_dst))

    _make_routing_json(dl_dir / "routing.json")
    _make_tools_json(dl_dir / "tools.json")

    for tool_name, subdir_name in _MOCK_TOOLS:
        tool_dir = _ensure_dir(dl_dir / subdir_name)
        _create_tool_wrapper(tool_dir, tool_name, dispatcher_dst)


def _patch_root_resolving(monkeypatch, tmp_root):
    """Monkey-patch find_project_root and resolve_registered_tool so that
    tools are resolved from *tmp_root* instead of the real repo root."""
    import _common as _cm
    import router as _rt

    ext = _wrapper_ext()
    mock_tool_paths: dict[str, Path] = {}
    for tool_name, subdir_name in _MOCK_TOOLS:
        mock_tool_paths[tool_name] = tmp_root / "download-tools" / subdir_name / f"{tool_name}{ext}"

    _orig_find = _cm.find_project_root

    def _patched_find(start: Path | None = None) -> Path:
        cwd = Path.cwd().resolve()
        for parent in [cwd] + list(cwd.parents):
            if (
                (parent / "AGENT_READ_ME_FIRST.md").is_file()
                and (parent / "skill" / "mediaharbor" / "SKILL.md").is_file()
                and (parent / "download-tools" / "tools.json").is_file()
            ):
                return parent
        return _orig_find(start)

    monkeypatch.setattr(_cm, "find_project_root", _patched_find)
    monkeypatch.setattr(_rt, "find_project_root", _patched_find)

    _orig_resolve = _cm.resolve_registered_tool

    def _patched_resolve(name: str, registry=None, allow_system_path: bool = False):
        if name in mock_tool_paths and mock_tool_paths[name].is_file():
            return mock_tool_paths[name]
        return _orig_resolve(name, registry, allow_system_path)

    monkeypatch.setattr(_cm, "resolve_registered_tool", _patched_resolve)


def _task_by_url(project_name: str, url: str):
    from project import load_project

    proj = load_project(project_name)
    if proj is None:
        return None
    for t in proj.tasks:
        if t.url == url:
            return t
    return None


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


def test_success_path_ytdlp(monkeypatch, tmp_path_factory):
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-success", script="Integration test success")
        save_project(p)
        add_candidate("test-success", "https://example.com/video?id=1")

        from orchestrator import process_pending

        result = process_pending("test-success")

        assert result["processed"] == 1
        assert result["success"] == 1, f"Expected success, got: {result}"
        assert result["failed"] == 0

        task = _task_by_url("test-success", "https://example.com/video?id=1")
        assert task is not None
        assert task.status == "COMPLETED"
        assert task.backend == "yt-dlp"
        assert len(task.output_paths) == 1
        assert Path(task.output_paths[0]).is_file()

        from project import load_project

        proj = load_project("test-success")
        assert len(proj.materials) == 1
        assert proj.materials[0].verified is True
        assert proj.materials[0].format == "mp4"

        sources_dir = tmp_root / "output" / "test-success" / "acquisition" / "sources"
        source_files = list(sources_dir.glob("*.json"))
        assert len(source_files) >= 1
        src = json.loads(source_files[0].read_text(encoding="utf-8"))
        assert src["final_status"] == "SUCCESS"
        assert src["selected_backend"] == "yt-dlp"
        assert src["sha256"] is not None
        assert len(src["sha256"]) == 64
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_fallback_yutto(monkeypatch, tmp_path_factory):
    """yt-dlp download fails, yutto fallback succeeds."""
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-fallback", script="Fallback test")
        save_project(p)
        add_candidate("test-fallback", "https://www.bilibili.com/video/BV1xx")

        call_idx: list[int] = [0]

        from process_runner import ProcessRunner

        _orig = ProcessRunner._run_once

        def _patched(self, cmd, check_drm):
            from process_runner import ProcessResult

            call_idx[0] += 1
            n = call_idx[0]
            if n == 1:
                return _orig(self, cmd, check_drm)
            if n == 2:
                return ProcessResult(
                    returncode=1,
                    stdout="",
                    stderr="yt-dlp download failed",
                    elapsed=0.01,
                    status="DOWNLOAD_FAILED",
                )
            return _orig(self, cmd, check_drm)

        ProcessRunner._run_once = _patched
        try:
            from orchestrator import process_pending

            result = process_pending("test-fallback")
        finally:
            ProcessRunner._run_once = _orig

        assert result["processed"] == 1
        assert result["success"] == 1, f"Fallback test failed: {result}"
        task = _task_by_url("test-fallback", "https://www.bilibili.com/video/BV1xx")
        assert task is not None
        assert task.status == "COMPLETED", f"Expected COMPLETED, got {task.status}"
        assert task.backend == "yutto", f"Expected yutto backend, got {task.backend}"
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_all_backends_fail(monkeypatch, tmp_path_factory):
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)
    monkeypatch.setenv("MOCK_EXIT_CODE", "1")

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-all-fail", script="All fail")
        save_project(p)
        add_candidate("test-all-fail", "https://example.com/video?id=3")

        from orchestrator import process_pending

        result = process_pending("test-all-fail")

        assert result["processed"] == 1
        assert result["success"] == 0
        assert result["failed"] == 1

        task = _task_by_url("test-all-fail", "https://example.com/video?id=3")
        assert task is not None
        assert task.status == "FAILED"

        from project import load_project

        assert len(load_project("test-all-fail").materials) == 0
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_single_task_failure_continues(monkeypatch, tmp_path_factory):
    """A download failure in one task does not stop the queue."""
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-continue", script="Continue")
        save_project(p)
        add_candidate("test-continue", "https://www.bilibili.com/video/BV1fail")
        add_candidate("test-continue", "https://www.bilibili.com/video/BV1ok")

        call_idx: list[int] = [0]

        from process_runner import ProcessRunner

        _orig = ProcessRunner._run_once

        def _patched(self, cmd, check_drm):
            from process_runner import ProcessResult

            call_idx[0] += 1
            n = call_idx[0]
            if n in (2, 3):
                return ProcessResult(
                    returncode=1,
                    stdout="",
                    stderr="fails",
                    elapsed=0.01,
                    status="DOWNLOAD_FAILED",
                )
            return _orig(self, cmd, check_drm)

        ProcessRunner._run_once = _patched
        try:
            from orchestrator import process_pending

            result = process_pending("test-continue")
        finally:
            ProcessRunner._run_once = _orig

        assert result["processed"] == 2
        assert result["success"] >= 1
        assert result["failed"] >= 1

        t1 = _task_by_url("test-continue", "https://www.bilibili.com/video/BV1fail")
        t2 = _task_by_url("test-continue", "https://www.bilibili.com/video/BV1ok")
        assert t1 is not None and t1.status == "FAILED"
        assert t2 is not None and t2.status == "COMPLETED"
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_validation_failure_no_output_path(monkeypatch, tmp_path_factory):
    """Mock returns success but no file path in stdout -> task FAILED."""
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)
    monkeypatch.setenv("MOCK_SILENT_STDOUT", "1")

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-val-fail", script="Val fail")
        save_project(p)
        add_candidate("test-val-fail", "https://example.com/video?id=valfail")

        from orchestrator import process_pending

        result = process_pending("test-val-fail")

        assert result["processed"] == 1
        assert result["success"] == 0
        assert result["failed"] == 1

        task = _task_by_url("test-val-fail", "https://example.com/video?id=valfail")
        assert task is not None
        assert task.status == "FAILED"
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_drm_stops_fallback(monkeypatch, tmp_path_factory):
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)
    monkeypatch.setenv("MOCK_TOOL_STATUS", "ERROR: Widevine DRM detected")
    monkeypatch.setenv("MOCK_EXIT_CODE", "1")

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-drm", script="DRM")
        save_project(p)
        add_candidate("test-drm", "https://www.bilibili.com/video/BV1drm")

        from orchestrator import process_pending

        result = process_pending("test-drm")

        assert result["processed"] == 1
        assert result["success"] == 0
        assert result["failed"] == 1

        task = _task_by_url("test-drm", "https://www.bilibili.com/video/BV1drm")
        assert task is not None
        assert task.status == "FAILED"
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_auth_stops_fallback(monkeypatch, tmp_path_factory):
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)
    monkeypatch.setenv("MOCK_TOOL_STATUS", "ERROR: Sign in is required")
    monkeypatch.setenv("MOCK_EXIT_CODE", "1")

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-auth", script="Auth")
        save_project(p)
        add_candidate("test-auth", "https://example.com/video?id=auth")

        from orchestrator import process_pending

        result = process_pending("test-auth")

        assert result["processed"] == 1
        assert result["success"] == 0
        assert result["failed"] == 1

        task = _task_by_url("test-auth", "https://example.com/video?id=auth")
        assert task is not None
        assert task.status == "FAILED"
        assert task.error is not None
        assert "AUTH" in task.error.upper()
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_geo_stops_fallback(monkeypatch, tmp_path_factory):
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)
    monkeypatch.setenv("MOCK_TOOL_STATUS", "ERROR: This content is geo-restricted")
    monkeypatch.setenv("MOCK_EXIT_CODE", "1")

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-geo", script="GEO")
        save_project(p)
        add_candidate("test-geo", "https://example.com/video?id=geo")

        from orchestrator import process_pending

        result = process_pending("test-geo")

        assert result["processed"] == 1
        assert result["success"] == 0
        assert result["failed"] == 1

        task = _task_by_url("test-geo", "https://example.com/video?id=geo")
        assert task is not None
        assert task.status == "FAILED"
        assert task.error is not None
        assert "GEO" in task.error.upper()
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_source_json_state_consistency(monkeypatch, tmp_path_factory):
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-consistency", script="Consistency")
        save_project(p)
        add_candidate("test-consistency", "https://example.com/video?id=ok1")

        from orchestrator import process_pending

        result = process_pending("test-consistency")
        assert result["success"] == 1

        task = _task_by_url("test-consistency", "https://example.com/video?id=ok1")
        assert task is not None
        assert task.status == "COMPLETED"

        sources_dir = tmp_root / "output" / "test-consistency" / "acquisition" / "sources"
        source_files = list(sources_dir.glob("*.json"))
        assert len(source_files) >= 1

        src = json.loads(source_files[0].read_text(encoding="utf-8"))
        assert src["final_status"] == "SUCCESS"
        assert src["sha256"] is not None
        assert len(src["local_files"]) >= 1
        assert Path(src["local_files"][0]).is_file()
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_sanitized_url_skipped(monkeypatch, tmp_path_factory):
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-redacted", script="Redacted")
        save_project(p)
        add_candidate("test-redacted", "https://example.com/video?token=secret")

        from orchestrator import process_pending

        result = process_pending("test-redacted")

        task = _task_by_url("test-redacted", "https://example.com/video?token=REDACTED")
        assert task is not None
        assert task.status == "SKIPPED"
        assert result["failed"] == 1
        assert result["processed"] == 0
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_missing_tool_degrades_to_fallback(monkeypatch, tmp_path_factory):
    """When the preferred backend tool is missing on disk, processing degrades
    to the next backend instead of aborting the task."""
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)

    # Simulate yt-dlp being unavailable on disk. We patch the resolver directly
    # (rather than deleting the wrapper) because backend modules capture their
    # resolve_* reference at import time, so file deletion would not be seen by
    # already-imported modules in the shared test session.
    import ytdlp_adapter

    monkeypatch.setattr(ytdlp_adapter, "resolve_ytdlp", lambda allow_system_path=False: None)

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-missing", script="Missing")
        save_project(p)
        add_candidate("test-missing", "https://www.bilibili.com/video/BV1miss")

        from orchestrator import process_pending

        result = process_pending("test-missing")

        assert result["processed"] == 1
        assert result["success"] == 1, f"Expected fallback success, got: {result}"
        assert result["failed"] == 0

        task = _task_by_url("test-missing", "https://www.bilibili.com/video/BV1miss")
        assert task is not None
        assert task.status == "COMPLETED"
        assert task.backend == "yutto", f"Expected yutto fallback, got {task.backend}"
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_retry_budget_enforced(monkeypatch, tmp_path_factory):
    """The global attempt budget caps fallback: remaining backends are not
    tried and the task fails without exceeding the budget."""
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)
    monkeypatch.setenv("MOCK_EXIT_CODE", "1")

    import process_runner as _pr
    import router as _rt

    # Cap the budget low enough to fire before all (max_backends=3) backends run.
    monkeypatch.setattr(_pr, "MAX_TOTAL_ATTEMPTS", 2)
    monkeypatch.setattr(_rt, "MAX_TOTAL_ATTEMPTS", 2)
    # Skip the live probe so the budget only governs download attempts.
    monkeypatch.setattr(_rt, "probe_and_resolve_live", lambda *a, **k: (None, None))

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-budget", script="budget")
        save_project(p)
        add_candidate("test-budget", "https://example.com/video?id=budget")

        from process_runner import ProcessRunner

        calls: list[int] = [0]
        _orig = ProcessRunner._run_once

        def _patched(self, cmd, check_drm):
            calls[0] += 1
            return _orig(self, cmd, check_drm)

        ProcessRunner._run_once = _patched
        try:
            from orchestrator import process_pending

            result = process_pending("test-budget")
        finally:
            ProcessRunner._run_once = _orig

        assert result["processed"] == 1
        assert result["success"] == 0
        assert result["failed"] == 1

        task = _task_by_url("test-budget", "https://example.com/video?id=budget")
        assert task is not None
        assert task.status == "FAILED"
        assert task.error is not None
        # Budget of 2 with route max_retries=1 -> exactly 2 backend attempts;
        # without the budget the vod route (max_backends=3) would run 3.
        assert calls[0] == 2, f"Budget not enforced: got {calls[0]} attempts"
        assert "RATE_LIMITED" in task.error or "attempt limit" in task.error.lower()
    finally:
        monkeypatch.chdir(str(old_cwd))


def test_multi_file_artifacts(monkeypatch, tmp_path_factory):
    """A backend that writes the media file plus sidecar artifacts (info json,
    thumbnail, subtitle) completes successfully, the media file is registered
    as the task's material, and all artifacts survive in the output dir."""
    tmp_root = tmp_path_factory.mktemp("mh_int")
    _setup_environment(tmp_root)
    old_cwd = Path.cwd().resolve()
    monkeypatch.chdir(tmp_root)
    _patch_root_resolving(monkeypatch, tmp_root)
    monkeypatch.setenv("MOCK_WRITE_SIDECARS", "1")

    try:
        from acquisition import add_candidate
        from project import create_project, save_project

        p = create_project("test-multifile", script="Multi-file artifacts")
        save_project(p)
        add_candidate("test-multifile", "https://example.com/video?id=multi")

        from orchestrator import process_pending

        result = process_pending("test-multifile")

        assert result["processed"] == 1
        assert result["success"] == 1, f"Expected success, got: {result}"
        assert result["failed"] == 0

        task = _task_by_url("test-multifile", "https://example.com/video?id=multi")
        assert task is not None
        assert task.status == "COMPLETED"
        assert task.backend == "yt-dlp"
        assert len(task.output_paths) == 1
        media_path = Path(task.output_paths[0])
        assert media_path.is_file()

        from project import load_project

        proj = load_project("test-multifile")
        assert len(proj.materials) == 1
        assert proj.materials[0].verified is True
        assert Path(proj.materials[0].local_path) == media_path

        output_dir = media_path.parent
        stem = media_path.stem
        for ext in ("info.json", "jpg", "srt"):
            side = output_dir / f"{stem}.{ext}"
            assert side.is_file(), f"Missing sidecar artifact: {side}"

        sources_dir = tmp_root / "output" / "test-multifile" / "acquisition" / "sources"
        source_files = list(sources_dir.glob("*.json"))
        assert len(source_files) >= 1
        src = json.loads(source_files[0].read_text(encoding="utf-8"))
        assert src["final_status"] == "SUCCESS"
        assert src["selected_backend"] == "yt-dlp"
        assert Path(src["local_files"][0]) == media_path

        reports_dir = tmp_root / "output" / "test-multifile" / "reports"
        assert (reports_dir / "COVERAGE_REPORT.md").is_file()
        assert (reports_dir / "HUMAN_EDITOR_HANDOFF.md").is_file()
        report_text = (reports_dir / "COVERAGE_REPORT.md").read_text(encoding="utf-8")
        assert "**Completed:** 1" in report_text
        assert str(media_path) in report_text
    finally:
        monkeypatch.chdir(str(old_cwd))
