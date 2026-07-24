from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "skill" / "mediaharbor" / "scripts")
)
from router import (
    RouteEntry,
    _builtin_routes,
    download_with_fallback,
    execute_backend,
    match_route,
)


def test_builtin_routes_loaded():
    routes = _builtin_routes()
    assert len(routes) >= 3
    names = [r.name for r in routes]
    assert "bilibili" in names
    assert "vod" in names
    assert "social" in names


def test_match_bilibili_url():
    routes = _builtin_routes()
    route = match_route("https://www.bilibili.com/video/BV1xx", routes)
    assert route is not None
    assert route.name == "bilibili"
    assert route.backends[0] == "yt-dlp"


def test_match_b23_url():
    routes = _builtin_routes()
    route = match_route("https://b23.tv/abc123", routes)
    assert route is not None
    assert route.name == "bilibili"


def test_match_vod_url():
    routes = _builtin_routes()
    route = match_route("https://www.youtube.com/watch?v=test123", routes)
    assert route is not None
    assert route.name == "vod"


def test_match_hls_url():
    routes = _builtin_routes()
    route = match_route("https://example.com/stream.m3u8", routes)
    assert route is not None
    assert route.name == "hls-dash"


def test_match_social_twitter():
    routes = _builtin_routes()
    route = match_route("https://twitter.com/user/status/123", routes)
    assert route is not None
    assert route.name == "social"


def test_match_social_xcom():
    routes = _builtin_routes()
    route = match_route("https://x.com/user/status/456", routes)
    assert route is not None
    assert route.name == "social"


def test_no_match_unknown():
    routes = _builtin_routes()
    route = match_route("ftp://files.example.com/video.mp4", routes)
    assert route is None


def test_unknown_backend_returns_unsupported():

    result = execute_backend("nonexistent-backend", "https://example.com", Path("/tmp"))
    assert result.status == "UNSUPPORTED_URL"


def test_download_fallback_no_route():
    routes = _builtin_routes()
    result, backend = download_with_fallback(
        "ftp://files.example.com/video.mp4", Path("/tmp/out"), routes=routes
    )
    assert result.status == "UNSUPPORTED_URL"
    assert backend is None


def test_bilibili_backends_order():
    routes = _builtin_routes()
    route = match_route("https://www.bilibili.com/video/BV1xx", routes)
    assert route.backends[0] == "yt-dlp"
    assert route.backends[1] == "yutto"


def test_global_budget_exhausted_across_backends(monkeypatch):
    from process_runner import BUDGET_EXHAUSTED, AttemptInfo, ProcessResult, ProcessRunner

    fake_attempts_pool = [
        AttemptInfo(n, "fake", "DOWNLOAD_FAILED", 1, 0.1, True, 0.0, "fake") for n in range(1, 6)
    ]
    call_count = 0
    last_runner_max = None

    def fake_execute(backend_name, url, output_dir, runner=None):
        nonlocal call_count, last_runner_max
        call_count += 1
        max_r = runner.max_retries if runner else 5
        last_runner_max = max_r
        return ProcessResult(
            returncode=1,
            stdout="",
            stderr="fake fail",
            status="DOWNLOAD_FAILED",
            attempts=list(fake_attempts_pool[:max_r]),
        )

    monkeypatch.setattr("router.execute_backend", fake_execute)
    monkeypatch.setattr("router.MAX_TOTAL_ATTEMPTS", 6)

    route = RouteEntry(
        name="test",
        patterns=[".*"],
        backends=["yt-dlp", "yutto", "gallery-dl"],
        max_retries=5,
    )
    runner = ProcessRunner(max_retries=5, sleep_fn=lambda s: None)
    result, last_backend = download_with_fallback(
        "https://example.com/video",
        Path("/tmp/out"),
        routes=[route],
        max_backends=3,
        runner=runner,
    )
    assert result.status == BUDGET_EXHAUSTED
    assert last_backend == "gallery-dl"
    assert len(result.attempts) == 6
    assert last_runner_max == 1


def test_remaining_budget_one_caps_backend(monkeypatch):
    from process_runner import AttemptInfo, ProcessResult, ProcessRunner

    fake_attempts = [
        AttemptInfo(n, "fake", "DOWNLOAD_FAILED", 1, 0.1, True, 0.0, "fake") for n in range(1, 6)
    ]

    def fake_execute(backend_name, url, output_dir, runner=None):
        max_r = runner.max_retries
        attempts = fake_attempts[:max_r]
        return ProcessResult(
            returncode=1,
            stdout="",
            stderr="fake fail",
            status="DOWNLOAD_FAILED",
            attempts=attempts,
        )

    monkeypatch.setattr("router.execute_backend", fake_execute)
    monkeypatch.setattr("router.MAX_TOTAL_ATTEMPTS", 6)

    route = RouteEntry(name="test", patterns=[".*"], backends=["yt-dlp", "yutto"], max_retries=5)
    runner = ProcessRunner(max_retries=5, sleep_fn=lambda s: None)
    result, last_backend = download_with_fallback(
        "https://example.com/video",
        Path("/tmp/out"),
        routes=[route],
        runner=runner,
    )
    assert len(result.attempts) == 6
    assert last_backend == "yutto"
    assert result.status == "DOWNLOAD_FAILED"


def test_terminal_status_stops_fallback_immediately(monkeypatch):
    from process_runner import AttemptInfo, ProcessResult, ProcessRunner

    call_count = 0

    def fake_execute(backend_name, url, output_dir, runner=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ProcessResult(
                returncode=1,
                stdout="",
                stderr="DRM detected",
                status="DRM_DETECTED",
                attempts=[AttemptInfo(1, backend_name, "DRM_DETECTED", 1, 0.1, False, 0.0, "DRM")],
            )
        return ProcessResult(
            returncode=1,
            stdout="",
            stderr="fail",
            status="DOWNLOAD_FAILED",
            attempts=[AttemptInfo(1, backend_name, "DOWNLOAD_FAILED", 1, 0.1, True, 0.0, "fail")],
        )

    monkeypatch.setattr("router.execute_backend", fake_execute)

    route = RouteEntry(name="test", patterns=[".*"], backends=["yt-dlp", "yutto"], max_retries=3)
    runner = ProcessRunner(max_retries=3, sleep_fn=lambda s: None)
    result, backend_name = download_with_fallback(
        "https://example.com/video",
        Path("/tmp/out"),
        routes=[route],
        runner=runner,
    )
    assert result.status == "DRM_DETECTED"
    assert backend_name == "yt-dlp"
    assert call_count == 1
