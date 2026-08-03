from __future__ import annotations

import json
from pathlib import Path

from _common import resolve_registered_tool
from process_runner import ProcessResult, ProcessRunner


def resolve_ffprobe(allow_system_path: bool = False) -> Path | None:
    try:
        result = resolve_registered_tool("ffprobe", allow_system_path=allow_system_path)
        if result:
            return result
    except Exception:
        pass
    if allow_system_path:
        import shutil

        system = shutil.which("ffprobe")
        if system:
            return Path(system)
    return None


def validate_media(file_path: Path, runner: ProcessRunner | None = None) -> ProcessResult:
    if runner is None:
        runner = ProcessRunner()
    ffprobe = resolve_ffprobe()
    if ffprobe is None:
        return ProcessResult(
            returncode=-1, stdout="", stderr="ffprobe not found", status="TOOL_MISSING"
        )
    cmd = [
        str(ffprobe),
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    return runner.run(cmd, backend="ffprobe")


def validate_downloaded_file(file_path: Path, output_dir: Path) -> ProcessResult:
    if not file_path.is_file() or file_path.stat().st_size == 0:
        return ProcessResult(
            returncode=-1,
            stdout="",
            stderr="File missing or empty",
            status="VALIDATION_FAILED",
        )
    try:
        file_path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        return ProcessResult(
            returncode=-1,
            stdout="",
            stderr="File outside output dir",
            status="VALIDATION_FAILED",
        )

    result = validate_media(file_path)
    if result.status != "SUCCESS":
        return result
    info = parse_ffprobe_output(result.stdout)
    media = get_media_info(info) if info else None
    if not media or media["duration"] <= 0 or not media["has_video"]:
        result.status = "VALIDATION_FAILED"
    return result


def parse_ffprobe_output(stdout: str) -> dict | None:
    if not stdout.strip():
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def _parse_fps(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        if "/" in raw:
            num, _, den = raw.partition("/")
            den = den or "1"
            return float(num) / float(den)
        return float(raw)
    except (ValueError, ZeroDivisionError):
        return None


def get_media_info(data: dict) -> dict:
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    duration = float(fmt.get("duration", 0))
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    width = video_streams[0].get("width") if video_streams else None
    height = video_streams[0].get("height") if video_streams else None
    return {
        "format_name": fmt.get("format_name", ""),
        "duration": duration,
        "size": int(fmt.get("size", 0)),
        "bit_rate": int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None,
        "width": width,
        "height": height,
        "fps": _parse_fps(video_streams[0].get("avg_frame_rate")) if video_streams else None,
        "video_bitrate": (
            int(video_streams[0]["bit_rate"])
            if video_streams and video_streams[0].get("bit_rate")
            else None
        ),
        "orientation": (
            "vertical"
            if width and height and height > width
            else "landscape"
            if width and height
            else None
        ),
        "video_codec": video_streams[0].get("codec_name") if video_streams else None,
        "audio_codec": audio_streams[0].get("codec_name") if audio_streams else None,
        "has_video": len(video_streams) > 0,
        "has_audio": len(audio_streams) > 0,
    }
