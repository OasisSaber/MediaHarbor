from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "skill" / "mediaharbor" / "scripts")
)

from process_runner import SUCCESS, AttemptInfo, BackendResult


def _mock_success_result() -> MagicMock:
    return MagicMock(
        status=SUCCESS,
        returncode=0,
        stdout="",
        stderr="",
        attempts=[
            AttemptInfo(1, "test", SUCCESS, 0, 1.0, False, ""),
        ],
    )


def _make_file(output_dir: Path, name: str) -> Path:
    p = output_dir / name
    p.write_text("fake content")
    return p


class TestStreamlinkContract:
    def test_tool_missing_returns_backend_result(self):
        from backends.streamlink import run_streamlink

        result = run_streamlink("https://example.com/live", Path("/tmp/nonexistent"))
        assert isinstance(result, BackendResult)
        assert result.status == "TOOL_MISSING"
        assert result.output_paths == []

    @patch("backends.streamlink.resolve_streamlink")
    @patch("process_runner.ProcessRunner.run")
    def test_success_discovers_output(self, mock_run, mock_resolve):
        from backends.streamlink import run_streamlink

        mock_resolve.return_value = Path("/fake/streamlink")
        mock_run.return_value = _mock_success_result()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            f = _make_file(output_dir, "stream.ts")
            result = run_streamlink("https://example.com/live", output_dir)
            assert result.status == SUCCESS
            assert f in result.output_paths

    @patch("backends.streamlink.resolve_streamlink")
    @patch("process_runner.ProcessRunner.run")
    def test_success_no_file_yields_empty_paths(self, mock_run, mock_resolve):
        from backends.streamlink import run_streamlink

        mock_resolve.return_value = Path("/fake/streamlink")
        mock_run.return_value = _mock_success_result()

        with tempfile.TemporaryDirectory() as tmp:
            result = run_streamlink("https://example.com/live", Path(tmp))
            assert result.status == SUCCESS
            assert result.output_paths == []


class TestYuttoContract:
    def test_tool_missing_returns_backend_result(self):
        from backends.yutto import run_yutto

        result = run_yutto("https://www.bilibili.com/video/BV1xx", Path("/tmp/nonexistent"))
        assert isinstance(result, BackendResult)
        assert result.status == "TOOL_MISSING"

    @patch("backends.yutto.resolve_yutto")
    @patch("process_runner.ProcessRunner.run")
    def test_success_discovers_output(self, mock_run, mock_resolve):
        from backends.yutto import run_yutto

        mock_resolve.return_value = Path("/fake/yutto")
        mock_run.return_value = _mock_success_result()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            f1 = _make_file(output_dir, "video.mp4")
            f2 = _make_file(output_dir, "subtitle.ass")
            result = run_yutto("https://www.bilibili.com/video/BV1xx", output_dir)
            assert result.status == SUCCESS
            assert f1 in result.output_paths
            assert f2 in result.output_paths


class TestNm3u8dlreContract:
    def test_tool_missing_returns_backend_result(self):
        from backends.n_m3u8dl_re import run_n_m3u8dl_re

        result = run_n_m3u8dl_re("https://example.com/stream.m3u8", Path("/tmp/nonexistent"))
        assert isinstance(result, BackendResult)
        assert result.status == "TOOL_MISSING"

    @patch("backends.n_m3u8dl_re.resolve_n_m3u8dl_re")
    @patch("process_runner.ProcessRunner.run")
    def test_success_discovers_output(self, mock_run, mock_resolve):
        from backends.n_m3u8dl_re import run_n_m3u8dl_re

        mock_resolve.return_value = Path("/fake/n_m3u8dl_re")
        mock_run.return_value = _mock_success_result()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            f = _make_file(output_dir, "output.mp4")
            result = run_n_m3u8dl_re("https://example.com/stream.m3u8", output_dir)
            assert result.status == SUCCESS
            assert f in result.output_paths


class TestGalleryDlContract:
    def test_tool_missing_returns_backend_result(self):
        from backends.gallery_dl import run_gallery_dl

        result = run_gallery_dl("https://twitter.com/user/status/123", Path("/tmp/nonexistent"))
        assert isinstance(result, BackendResult)
        assert result.status == "TOOL_MISSING"

    @patch("backends.gallery_dl.resolve_gallery_dl")
    @patch("process_runner.ProcessRunner.run")
    def test_success_discovers_output(self, mock_run, mock_resolve):
        from backends.gallery_dl import run_gallery_dl

        mock_resolve.return_value = Path("/fake/gallery-dl")
        mock_run.return_value = _mock_success_result()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            f1 = _make_file(output_dir, "image.jpg")
            f2 = _make_file(output_dir, "image.png")
            result = run_gallery_dl("https://twitter.com/user/status/123", output_dir)
            assert result.status == SUCCESS
            assert f1 in result.output_paths
            assert f2 in result.output_paths


class TestYtdlpAdapterContract:
    def test_tool_missing_returns_backend_result(self):
        from ytdlp_adapter import download_url

        result = download_url("https://youtube.com/watch?v=test", Path("/tmp/nonexistent"))
        assert isinstance(result, BackendResult)
        assert result.status == "TOOL_MISSING"

    @patch("ytdlp_adapter.resolve_ytdlp")
    @patch("process_runner.ProcessRunner.run")
    def test_success_from_stdout_paths_and_dir_scan(self, mock_run, mock_resolve):
        from ytdlp_adapter import download_url

        mock_resolve.return_value = Path("/fake/yt-dlp")
        mock_run.return_value = _mock_success_result()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            main_file = _make_file(output_dir, "youtube-test123.mp4")
            result = download_url("https://youtube.com/watch?v=test", output_dir)
            assert result.status == SUCCESS
            assert main_file in result.output_paths

    @patch("ytdlp_adapter.resolve_ytdlp")
    @patch("process_runner.ProcessRunner.run")
    def test_classifies_media_types(self, mock_run, mock_resolve):
        from ytdlp_adapter import download_url

        mock_resolve.return_value = Path("/fake/yt-dlp")
        # Simulate --print after_move:filepath output
        success = _mock_success_result()
        success.stdout = f"{Path('/tmp/youtube-test123.mp4')}\n"
        mock_run.return_value = success

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            main = _make_file(output_dir, "youtube-test123.mp4")
            sub = _make_file(output_dir, "youtube-test123.en.vtt")
            thumb = _make_file(output_dir, "youtube-test123.webp")
            info = _make_file(output_dir, "youtube-test123.info.json")
            result = download_url("https://youtube.com/watch?v=test", output_dir)
            assert result.status == SUCCESS
            assert len(result.output_paths) == 4
            mt = result.metadata.get("media_types", {})
            assert main.name in [Path(p).name for p in mt.get("main", [])]
            assert sub.name in [Path(p).name for p in mt.get("subtitle", [])]
            assert thumb.name in [Path(p).name for p in mt.get("thumbnail", [])]
            assert info.name in [Path(p).name for p in mt.get("info_json", [])]
