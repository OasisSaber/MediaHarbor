from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "bagitup" / "scripts"))

from process_runner import SUCCESS, AttemptInfo, BackendResult, ProcessResult


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
    @patch("backends.streamlink.resolve_streamlink", return_value=None)
    def test_tool_missing_returns_backend_result(self, mock_resolve, tmp_path):
        from backends.streamlink import run_streamlink

        result = run_streamlink("https://example.com/live", tmp_path)
        assert isinstance(result, BackendResult)
        assert result.status == "TOOL_MISSING"
        assert result.output_paths == []

    @patch("backends.streamlink.resolve_streamlink")
    @patch("process_runner.ProcessRunner.run")
    def test_success_no_file_yields_empty_paths(self, mock_run, mock_resolve):
        from backends.streamlink import run_streamlink

        mock_resolve.return_value = Path("/fake/streamlink")
        mock_run.return_value = _mock_success_result()

        with tempfile.TemporaryDirectory() as tmp:
            result = run_streamlink("https://example.com/live", Path(tmp))
            assert result.status == "VALIDATION_FAILED"
            assert result.output_paths == []
            assert "no output files" in result.stderr

    @patch("backends.streamlink.resolve_streamlink")
    def test_success_excludes_preexisting_output(self, mock_resolve, tmp_path):
        from backends.streamlink import run_streamlink

        mock_resolve.return_value = Path("/fake/streamlink")
        stale = _make_file(tmp_path, "stale.mp4")

        class WritingRunner:
            def run(self, cmd, **_kwargs):
                Path(cmd[-1]).write_text("new stream")
                return ProcessResult(
                    returncode=0,
                    stdout="",
                    stderr="",
                    status=SUCCESS,
                )

        result = run_streamlink(
            "https://example.com/live",
            tmp_path,
            runner=WritingRunner(),
        )

        assert result.output_paths == [tmp_path / "stream.ts"]
        assert stale not in result.output_paths


def test_backend_result_bounds_and_sanitizes_stderr():
    result = BackendResult(
        status="DOWNLOAD_FAILED",
        stderr="https://example.com/video?token=secret " + ("x" * 3000),
    )

    assert "secret" not in result.stderr
    assert len(result.stderr) <= 2000


def test_sanitize_redacts_credential_parameters():
    from process_runner import sanitize_stderr, sanitize_url

    url = (
        "https://storage.example.com/video.mp4?"
        "X-Goog-Credential=svc%40proj.iam.gserviceaccount.com%2F2026%2F08%2F04%2Fauto"
        "&X-Goog-Signature=abc123signature"
    )
    cleaned = sanitize_url(url)
    assert "svc%40proj.iam" not in cleaned
    assert "abc123signature" not in cleaned
    assert "REDACTED" in cleaned

    err = (
        "failed fetching https://example.com/v?"
        "x-amz-credential=AKIAEXAMPLE123&x-amz-signature=deadbeef"
    )
    redacted = sanitize_stderr(err)
    assert "AKIAEXAMPLE123" not in redacted
    assert "deadbeef" not in redacted

    password_err = "https://example.com/login?password=hunter2&passwd=secret3"
    redacted_pw = sanitize_stderr(password_err)
    assert "hunter2" not in redacted_pw
    assert "secret3" not in redacted_pw

    nested = "https://example.com/redirect?next=https://cdn.example.com/v?token=NESTEDSECRET"
    redacted_nested = sanitize_url(nested)
    assert "NESTEDSECRET" not in redacted_nested
    assert "REDACTED" in redacted_nested

    fragment = "https://example.com/callback#token=FRAGMENTSECRET&x=1"
    redacted_fragment = sanitize_url(fragment)
    assert "FRAGMENTSECRET" not in redacted_fragment
    assert "REDACTED" in redacted_fragment

    query_fragment = "https://example.com/callback?a=1#token=QFSECRET"
    redacted_qf = sanitize_url(query_fragment)
    assert "QFSECRET" not in redacted_qf
    assert "REDACTED" in redacted_qf

    long_nested = (
        "https://example.com/redirect?next="
        + ("a" * 100)
        + "?token=LONGNESTEDSECRET%26"
        + ("b" * 40)
    )
    redacted_long = sanitize_url(long_nested)
    assert "LONGNESTEDSECRET" not in redacted_long
    assert "token=" not in redacted_long
    assert "..." in redacted_long


class TestYuttoContract:
    @patch("backends.yutto.resolve_yutto", return_value=None)
    def test_tool_missing_returns_backend_result(self, mock_resolve, tmp_path):
        from backends.yutto import run_yutto

        result = run_yutto("https://www.bilibili.com/video/BV1xx", tmp_path)
        assert isinstance(result, BackendResult)
        assert result.status == "TOOL_MISSING"


class TestNm3u8dlreContract:
    @patch("backends.n_m3u8dl_re.resolve_n_m3u8dl_re", return_value=None)
    def test_tool_missing_returns_backend_result(self, mock_resolve, tmp_path):
        from backends.n_m3u8dl_re import run_n_m3u8dl_re

        result = run_n_m3u8dl_re("https://example.com/stream.m3u8", tmp_path)
        assert isinstance(result, BackendResult)
        assert result.status == "TOOL_MISSING"


class TestGalleryDlContract:
    @patch("backends.gallery_dl.resolve_gallery_dl", return_value=None)
    def test_tool_missing_returns_backend_result(self, mock_resolve, tmp_path):
        from backends.gallery_dl import run_gallery_dl

        result = run_gallery_dl("https://twitter.com/user/status/123", tmp_path)
        assert isinstance(result, BackendResult)
        assert result.status == "TOOL_MISSING"


class TestYtdlpAdapterContract:
    @patch("ytdlp_adapter.resolve_ytdlp", return_value=None)
    def test_tool_missing_returns_backend_result(self, mock_resolve, tmp_path):
        from ytdlp_adapter import download_url

        result = download_url("https://youtube.com/watch?v=test", tmp_path)
        assert isinstance(result, BackendResult)
        assert result.status == "TOOL_MISSING"

    @patch("ytdlp_adapter.resolve_ytdlp")
    def test_classifies_media_types(self, mock_resolve, tmp_path):
        from ytdlp_adapter import download_url

        mock_resolve.return_value = Path("/fake/yt-dlp")
        names = [
            "youtube-test123.mp4",
            "youtube-test123.en.vtt",
            "youtube-test123.webp",
            "youtube-test123.info.json",
        ]

        class WritingRunner:
            def run(self, _cmd, **_kwargs):
                for name in names:
                    _make_file(tmp_path, name)
                return ProcessResult(
                    returncode=0,
                    stdout=f"{tmp_path / names[0]}\n",
                    stderr="",
                    status=SUCCESS,
                )

        result = download_url(
            "https://youtube.com/watch?v=test",
            tmp_path,
            runner=WritingRunner(),
        )

        assert result.status == SUCCESS
        assert len(result.output_paths) == 4
        media_types = result.metadata["media_types"]
        assert [Path(path).name for path in media_types["main"]] == [names[0]]
        assert [Path(path).name for path in media_types["subtitle"]] == [names[1]]
        assert [Path(path).name for path in media_types["thumbnail"]] == [names[2]]
        assert [Path(path).name for path in media_types["info_json"]] == [names[3]]

    @patch("ytdlp_adapter.resolve_ytdlp")
    def test_classifies_danmaku_as_info_json(self, mock_resolve, tmp_path):
        from ytdlp_adapter import download_url

        mock_resolve.return_value = Path("/fake/yt-dlp")
        names = [
            "BiliBili-BV1xxx.mp4",
            "BiliBili-BV1xxx.danmaku.xml",
            "BiliBili-BV1xxx.info.json",
        ]

        class WritingRunner:
            def run(self, _cmd, **_kwargs):
                for name in names:
                    _make_file(tmp_path, name)
                return ProcessResult(
                    returncode=0,
                    stdout=f"{tmp_path / names[0]}\n",
                    stderr="",
                    status=SUCCESS,
                )

        result = download_url(
            "https://www.bilibili.com/video/BV1xxx",
            tmp_path,
            runner=WritingRunner(),
        )

        assert result.status == SUCCESS
        media_types = result.metadata["media_types"]
        assert [Path(path).name for path in media_types["main"]] == [names[0]]
        assert [Path(path).name for path in media_types["info_json"]] == [
            names[1],
            names[2],
        ]

    @patch("ytdlp_adapter.resolve_ytdlp")
    def test_success_excludes_preexisting_output(self, mock_resolve, tmp_path):
        from ytdlp_adapter import download_url

        mock_resolve.return_value = Path("/fake/yt-dlp")
        stale = _make_file(tmp_path, "stale.mp4")
        current = tmp_path / "youtube-current.mp4"

        class WritingRunner:
            def run(self, _cmd, **_kwargs):
                current.write_text("current media")
                return ProcessResult(
                    returncode=0,
                    stdout=f"{current}\n",
                    stderr="",
                    status=SUCCESS,
                )

        result = download_url(
            "https://youtube.com/watch?v=current",
            tmp_path,
            runner=WritingRunner(),
        )

        assert result.output_paths == [current]
        assert stale not in result.output_paths


@pytest.mark.parametrize(
    ("module_name", "resolver_name", "run_name", "url"),
    [
        (
            "backends.yutto",
            "resolve_yutto",
            "run_yutto",
            "https://www.bilibili.com/video/BV1xx",
        ),
        (
            "backends.n_m3u8dl_re",
            "resolve_n_m3u8dl_re",
            "run_n_m3u8dl_re",
            "https://example.com/stream.m3u8",
        ),
        (
            "backends.gallery_dl",
            "resolve_gallery_dl",
            "run_gallery_dl",
            "https://twitter.com/user/status/123",
        ),
    ],
)
def test_directory_backends_exclude_preexisting_output(
    module_name,
    resolver_name,
    run_name,
    url,
    monkeypatch,
    tmp_path,
):
    module = importlib.import_module(module_name)
    monkeypatch.setattr(module, resolver_name, lambda: Path("/fake/tool"))
    stale = _make_file(tmp_path, "stale.mp4")
    current = tmp_path / "current.mp4"

    class WritingRunner:
        def run(self, _cmd, **_kwargs):
            current.write_text("current media")
            return ProcessResult(
                returncode=0,
                stdout="",
                stderr="",
                status=SUCCESS,
            )

    result = getattr(module, run_name)(url, tmp_path, runner=WritingRunner())

    assert result.output_paths == [current]
    assert stale not in result.output_paths
