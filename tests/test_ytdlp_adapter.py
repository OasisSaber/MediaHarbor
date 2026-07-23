from __future__ import annotations

from pathlib import Path

from ytdlp_adapter import build_download_args, build_probe_args


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
