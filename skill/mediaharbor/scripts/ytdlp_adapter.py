from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _common import find_project_root, resolve_registered_tool
from process_runner import (
    SUCCESS,
    ProcessResult,
    ProcessRunner,
    sanitize_url,
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
    if runner is None:
        runner = ProcessRunner()
    yt_path = resolve_ytdlp()
    if yt_path is None:
        return ProcessResult(
            returncode=-1, stdout="", stderr="yt-dlp not found", status="TOOL_MISSING"
        )
    cmd = [str(yt_path)] + build_probe_args(url)
    return runner.run(cmd, check_drm=True, backend="yt-dlp")


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
            "formats",
        ):
            if key in data:
                result[key] = data[key]
        if "webpage_url" in result:
            result["webpage_url"] = sanitize_url(result["webpage_url"])
        return result
    except (json.JSONDecodeError, IndexError):
        return None


def download_url(
    url: str,
    output_dir: Path,
    runner: ProcessRunner | None = None,
    allow_system_path: bool = False,
) -> ProcessResult:
    if runner is None:
        runner = ProcessRunner(timeout=DOWNLOAD_TIMEOUT, max_retries=2)
    yt_path = resolve_ytdlp(allow_system_path=allow_system_path)
    if yt_path is None:
        return ProcessResult(
            returncode=-1, stdout="", stderr="yt-dlp not found", status="TOOL_MISSING"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(yt_path)] + build_download_args(url, output_dir)
    result = runner.run(cmd, check_drm=True, backend="yt-dlp")
    return result


def validate_download_result(result: ProcessResult, output_dir: Path) -> ProcessResult:
    if result.status != SUCCESS:
        return result

    if not result.stdout.strip():
        result.status = "VALIDATION_FAILED"
        return result

    downloaded_path = result.stdout.strip().splitlines()[-1].strip()
    if not downloaded_path:
        result.status = "VALIDATION_FAILED"
        return result

    file_path = Path(downloaded_path)
    if not file_path.is_file() or file_path.stat().st_size == 0:
        result.status = "VALIDATION_FAILED"
        return result

    try:
        file_path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        result.status = "VALIDATION_FAILED"
        return result

    from ffprobe_validator import parse_ffprobe_output, validate_media

    probe_result = validate_media(file_path)
    if probe_result.status != SUCCESS:
        result.status = "VALIDATION_FAILED"
        return result

    info = parse_ffprobe_output(probe_result.stdout)
    if not info:
        result.status = "VALIDATION_FAILED"
        return result

    from ffprobe_validator import get_media_info

    media = get_media_info(info)
    if media["duration"] <= 0:
        result.status = "VALIDATION_FAILED"
        return result
    has_video = any(s.get("codec_type") == "video" for s in info.get("streams", []))
    if not has_video:
        result.status = "VALIDATION_FAILED"
        return result

    return result


DOWNLOAD_TIMEOUT = 600
