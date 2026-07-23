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


def parse_ffprobe_output(stdout: str) -> dict | None:
    if not stdout.strip():
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
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
        "video_codec": video_streams[0].get("codec_name") if video_streams else None,
        "audio_codec": audio_streams[0].get("codec_name") if audio_streams else None,
        "has_video": len(video_streams) > 0,
        "has_audio": len(audio_streams) > 0,
    }
