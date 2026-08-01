from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _common import find_project_root, resolve_registered_tool
from process_runner import (
    PROBE_TIMEOUT,
    SUCCESS,
    BackendResult,
    ProcessResult,
    ProcessRunner,
    discover_output_files,
    sanitize_url,
    snapshot_output_files,
)


def resolve_ytdlp(allow_system_path: bool = False) -> Path | None:
    try:
        result = resolve_registered_tool("yt-dlp", allow_system_path=allow_system_path)
        if result:
            return result
    except Exception:
        pass
    if allow_system_path:
        import shutil

        system = shutil.which("yt-dlp")
        if system:
            return Path(system)
    return None


def build_probe_args(url: str) -> list[str]:
    return ["--no-playlist", "--dump-json", "--skip-download", url]


def build_download_args(url: str, output_dir: Path) -> list[str]:
    template = output_dir / "%(extractor)s-%(id)s.%(ext)s"
    ffmpeg_dir = find_project_root() / "download-tools" / "ffmpeg"
    args = [
        "--no-playlist",
        "--format",
        "bv*+ba/b",
        "-o",
        str(template),
        "--print",
        "after_move:filepath",
        "--write-info-json",
        "--write-thumbnail",
        "--write-subs",
        "--write-auto-subs",
        "--no-overwrites",
    ]
    if ffmpeg_dir.is_dir():
        args.extend(["--ffmpeg-location", str(ffmpeg_dir)])
    args.append(url)
    return args


def probe_url(url: str, runner: ProcessRunner | None = None) -> ProcessResult:
    if runner is None or runner.timeout > PROBE_TIMEOUT:
        runner = ProcessRunner(timeout=PROBE_TIMEOUT)
    yt_path = resolve_ytdlp()
    if yt_path is None:
        return ProcessResult(
            returncode=-1, stdout="", stderr="yt-dlp not found", status="TOOL_MISSING"
        )
    cmd = [str(yt_path)] + build_probe_args(url)
    return runner.run(cmd, check_drm=True, backend="yt-dlp")


def _summarize_formats(formats: list[dict[str, Any]]) -> dict[str, Any]:
    heights = [f["height"] for f in formats if isinstance(f.get("height"), int)]
    fps = [f["fps"] for f in formats if isinstance(f.get("fps"), int)]
    bitrates = [f["tbr"] for f in formats if isinstance(f.get("tbr"), (int, float))]
    return {
        "count": len(formats),
        "max_height": max(heights) if heights else None,
        "max_fps": max(fps) if fps else None,
        "max_bitrate": max(bitrates) if bitrates else None,
    }


def parse_probe_json(output: str) -> dict[str, Any] | None:
    if not output.strip():
        return None
    try:
        data = json.loads(output.splitlines()[0])
        result = {}
        for key in (
            "id",
            "title",
            "ext",
            "duration",
            "webpage_url",
            "extractor",
            "is_live",
            "live_status",
        ):
            if key in data:
                result[key] = data[key]
        if "webpage_url" in result:
            result["webpage_url"] = sanitize_url(result["webpage_url"])
        if isinstance(data.get("formats"), list):
            result["formats_summary"] = _summarize_formats(data["formats"])
        return result
    except (json.JSONDecodeError, IndexError):
        return None


def _convert_to_backend_result(
    result: ProcessResult,
    output_dir: Path,
    before: dict[Path, tuple[int, int]] | None = None,
) -> BackendResult:
    output_paths: list[Path] = []
    if result.status == SUCCESS:
        discovered = discover_output_files(output_dir, before)
        discovered_by_resolved = {path.resolve(): path for path in discovered}
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if line:
                p = Path(line)
                discovered_path = discovered_by_resolved.get(p.resolve())
                if discovered_path is not None and discovered_path not in output_paths:
                    output_paths.append(discovered_path)
        for path in discovered:
            if path not in output_paths:
                output_paths.append(path)
    return BackendResult.from_process(result, output_paths)


def download_url(
    url: str,
    output_dir: Path,
    runner: ProcessRunner | None = None,
    allow_system_path: bool = False,
    max_attempts: int | None = None,
) -> BackendResult:
    if runner is None:
        runner = ProcessRunner(timeout=DOWNLOAD_TIMEOUT, max_retries=2)
    yt_path = resolve_ytdlp(allow_system_path=allow_system_path)
    if yt_path is None:
        return BackendResult(
            status="TOOL_MISSING",
            stderr="yt-dlp not found",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    before = snapshot_output_files(output_dir)
    cmd = [str(yt_path)] + build_download_args(url, output_dir)
    result = runner.run(cmd, check_drm=True, backend="yt-dlp", max_attempts=max_attempts)
    return _convert_to_backend_result(result, output_dir, before)


DOWNLOAD_TIMEOUT = 600
