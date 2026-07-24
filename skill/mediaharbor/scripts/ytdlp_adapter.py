from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _common import find_project_root, resolve_registered_tool
from process_runner import (
    SUCCESS,
    BackendResult,
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


def _classify_output_files(paths: list[Path]) -> dict[str, Any]:
    main: list[str] = []
    subtitles: list[str] = []
    thumbnails: list[str] = []
    info_jsons: list[str] = []
    for p in paths:
        name = p.name.lower()
        if name.endswith((".srt", ".vtt", ".ass", ".ssa", ".lrc")):
            subtitles.append(str(p))
        elif name.endswith((".jpg", ".jpeg", ".png", ".webp")):
            thumbnails.append(str(p))
        elif name.endswith(".info.json"):
            info_jsons.append(str(p))
        else:
            main.append(str(p))
    return {
        "main": main,
        "subtitle": subtitles,
        "thumbnail": thumbnails,
        "info_json": info_jsons,
    }


def _convert_to_backend_result(result: ProcessResult, output_dir: Path) -> BackendResult:
    output_paths: list[Path] = []
    if result.status == SUCCESS:
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if line:
                p = Path(line)
                if p.is_file():
                    output_paths.append(p)
        if output_dir.is_dir():
            for f in sorted(output_dir.iterdir()):
                if f.is_file() and f not in output_paths:
                    output_paths.append(f)
    metadata = {"media_types": _classify_output_files(output_paths)} if output_paths else {}
    return BackendResult(
        status=result.status,
        output_paths=output_paths,
        stdout=result.stdout,
        stderr=result.stderr,
        attempts=result.attempts,
        metadata=metadata,
    )


def download_url(
    url: str,
    output_dir: Path,
    runner: ProcessRunner | None = None,
    allow_system_path: bool = False,
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
    cmd = [str(yt_path)] + build_download_args(url, output_dir)
    result = runner.run(cmd, check_drm=True, backend="yt-dlp")
    return _convert_to_backend_result(result, output_dir)


DOWNLOAD_TIMEOUT = 600
