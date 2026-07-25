#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

_KNOWN_TOOLS = frozenset(
    {
        "yt-dlp",
        "yutto",
        "streamlink",
        "n-m3u8dl-re",
        "gallery-dl",
        "ffprobe",
    }
)


def _tool_name() -> str:
    if len(sys.argv) > 1 and sys.argv[1] in _KNOWN_TOOLS:
        return sys.argv[1]
    base = os.path.basename(sys.argv[0])
    for ext in (".bat", ".cmd", ".exe", ".py", ".sh"):
        if base.endswith(ext):
            base = base[: -len(ext)]
            break
    return base


def _remaining_args() -> list[str]:
    if len(sys.argv) > 1 and sys.argv[1] in _KNOWN_TOOLS:
        return sys.argv[2:]
    return sys.argv[1:]


def _make_fake_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"mock media content for integration testing")
    return path


def _exit_code() -> int:
    return int(os.environ.get("MOCK_EXIT_CODE", "0"))


def _emit_status_stderr():
    status = os.environ.get("MOCK_TOOL_STATUS", "")
    if status:
        print(status, file=sys.stderr)


def _find_url(args: list[str]) -> str:
    for a in args:
        if a.startswith("http"):
            return a
    return "https://example.com/mock"


def _mock_yt_dlp(args: list[str]) -> int:
    _emit_status_stderr()
    if "--dump-json" in args and "--skip-download" in args:
        url = _find_url(args)
        data = {
            "id": "mock001",
            "title": "Mock Video",
            "ext": "mp4",
            "duration": 30.0,
            "webpage_url": url,
            "extractor": "mock",
            "is_live": False,
            "live_status": "not_live",
        }
        json.dump(data, sys.stdout)
        return _exit_code()
    output_dir = None
    for i, a in enumerate(args):
        if a == "-o" and i + 1 < len(args):
            output_dir = str(Path(args[i + 1]).parent)
    if output_dir:
        output_name = os.environ.get("MOCK_OUTPUT_FILE", "mock_video.mp4")
        file_path = Path(output_dir) / output_name
        _make_fake_file(file_path)
        if os.environ.get("MOCK_WRITE_SIDECARS"):
            stem = Path(output_name).stem
            for ext in ("info.json", "jpg", "srt"):
                side = Path(output_dir) / f"{stem}.{ext}"
                side.write_bytes(b"mock sidecar artifact")
        if not os.environ.get("MOCK_SILENT_STDOUT"):
            print(str(file_path))
    return _exit_code()


def _mock_streamlink(args: list[str]) -> int:
    _emit_status_stderr()
    output_path = None
    for i, a in enumerate(args):
        if a == "-o" and i + 1 < len(args):
            output_path = args[i + 1]
            break
    if output_path:
        _make_fake_file(Path(output_path))
        if not os.environ.get("MOCK_SILENT_STDOUT"):
            print(output_path)
    return _exit_code()


def _mock_yutto(args: list[str]) -> int:
    _emit_status_stderr()
    output_dir = None
    for i, a in enumerate(args):
        if a == "-d" and i + 1 < len(args):
            output_dir = args[i + 1]
            break
    if output_dir:
        output_name = os.environ.get("MOCK_OUTPUT_FILE", "mock_video.mp4")
        file_path = Path(output_dir) / output_name
        _make_fake_file(file_path)
        if not os.environ.get("MOCK_SILENT_STDOUT"):
            print(str(file_path))
    return _exit_code()


def _mock_n_m3u8dl_re(args: list[str]) -> int:
    _emit_status_stderr()
    output_dir = None
    for i, a in enumerate(args):
        if a == "--save-dir" and i + 1 < len(args):
            output_dir = args[i + 1]
            break
    if output_dir:
        output_name = os.environ.get("MOCK_OUTPUT_FILE", "mock_video.mp4")
        file_path = Path(output_dir) / output_name
        _make_fake_file(file_path)
        if not os.environ.get("MOCK_SILENT_STDOUT"):
            print(str(file_path))
    return _exit_code()


def _mock_gallery_dl(args: list[str]) -> int:
    _emit_status_stderr()
    output_dir = None
    for i, a in enumerate(args):
        if a == "-d" and i + 1 < len(args):
            output_dir = args[i + 1]
            break
    if output_dir:
        output_name = os.environ.get("MOCK_OUTPUT_FILE", "mock_video.mp4")
        file_path = Path(output_dir) / output_name
        _make_fake_file(file_path)
        if not os.environ.get("MOCK_SILENT_STDOUT"):
            print(str(file_path))
    return _exit_code()


def _mock_ffprobe(args: list[str]) -> int:
    _emit_status_stderr()
    file_path = None
    for a in reversed(args):
        if not a.startswith("-"):
            file_path = a
            break
    if file_path and Path(file_path).is_file():
        data = {
            "streams": [
                {
                    "index": 0,
                    "codec_name": "h264",
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                },
                {"index": 1, "codec_name": "aac", "codec_type": "audio"},
            ],
            "format": {
                "filename": file_path,
                "format_name": "mp4",
                "duration": "30.000",
                "size": "1024",
                "bit_rate": "1000000",
            },
        }
        json.dump(data, sys.stdout)
    else:
        json.dump({"streams": [], "format": {}}, sys.stdout)
    return _exit_code()


_HANDLERS = {
    "yt-dlp": _mock_yt_dlp,
    "yutto": _mock_yutto,
    "streamlink": _mock_streamlink,
    "n-m3u8dl-re": _mock_n_m3u8dl_re,
    "gallery-dl": _mock_gallery_dl,
    "ffprobe": _mock_ffprobe,
}


def main() -> int:
    name = _tool_name()
    handler = _HANDLERS.get(name)
    if handler is None:
        print(f"Unknown mock tool: {name}", file=sys.stderr)
        return 1
    return handler(_remaining_args())


if __name__ == "__main__":
    sys.exit(main())
