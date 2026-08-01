from __future__ import annotations

import json
from pathlib import Path

from ytdlp_adapter import build_download_args, build_probe_args, parse_probe_json


def test_build_probe_args():
    args = build_probe_args("https://example.com/video")
    assert "--no-playlist" in args
    assert "--dump-json" in args
    assert "https://example.com/video" in args


def test_build_download_args():
    output_dir = Path("/tmp/test-out")
    args = build_download_args("https://example.com/video", output_dir)
    assert "--no-playlist" in args
    assert "--write-info-json" in args
    assert "--write-thumbnail" in args
    assert "-o" in args
    assert "https://example.com/video" in args


def test_parse_probe_json_returns_compact_summary():
    probe = {
        "id": "BV1xx411c7mD",
        "title": "Sample Video",
        "ext": "mp4",
        "duration": 123.4,
        "webpage_url": "https://www.bilibili.com/video/BV1xx411c7mD?token=secret",
        "extractor": "BiliBili",
        "is_live": False,
        "live_status": "not_live",
        "formats": [
            {"height": 1080, "fps": 60, "tbr": 5000.0},
            {"height": 720, "fps": 30, "tbr": 2500.0},
        ],
        "cookies": {"cookie": "value"},
        "headers": {"authorization": "Bearer x"},
        "url": "https://cdn.example.com/direct.mp4",
    }
    result = parse_probe_json(json.dumps(probe))
    assert result is not None
    assert result["id"] == "BV1xx411c7mD"
    assert result["title"] == "Sample Video"
    assert result["extractor"] == "BiliBili"
    assert result["duration"] == 123.4
    assert "formats" not in result
    assert "cookies" not in result
    assert "headers" not in result
    assert "url" not in result
    summary = result["formats_summary"]
    assert summary["count"] == 2
    assert summary["max_height"] == 1080
    assert summary["max_fps"] == 60
    assert summary["max_bitrate"] == 5000.0
    assert "token=REDACTED" in result["webpage_url"]
    assert "token=secret" not in result["webpage_url"]


def test_parse_probe_json_handles_missing_formats():
    result = parse_probe_json(json.dumps({"id": "x", "title": "no formats"}))
    assert result is not None
    assert result["id"] == "x"
    assert "formats_summary" not in result


def test_parse_probe_json_invalid_input():
    assert parse_probe_json("") is None
    assert parse_probe_json("not-json") is None
