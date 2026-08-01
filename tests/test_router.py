from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "skill" / "mediaharbor" / "scripts")
)
from process_runner import BackendResult
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
    assert isinstance(result, BackendResult)
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


def test_fallback_backends_use_isolated_attempt_directories(tmp_path, monkeypatch):
    import router

    route = RouteEntry(
        name="isolated-fallback",
        patterns=[r"example\.com"],
        backends=["yt-dlp", "streamlink"],
        max_retries=1,
    )
    attempt_dirs = []

    def fake_execute(backend_name, _url, output_dir, runner=None, max_attempts=None):
        del runner, max_attempts
        attempt_dirs.append(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        if backend_name == "yt-dlp":
            (output_dir / "partial.mp4").write_text("partial")
            return BackendResult(status="DOWNLOAD_FAILED")
        completed = output_dir / "stream.ts"
        completed.write_text("complete")
        return BackendResult(status="SUCCESS", output_paths=[completed])

    monkeypatch.setattr(router, "execute_backend", fake_execute)
    monkeypatch.setattr(router, "probe_and_resolve_live", lambda *_args, **_kwargs: (None, None))

    result, backend = download_with_fallback(
        "https://example.com/live",
        tmp_path,
        routes=[route],
    )

    assert result.status == "SUCCESS"
    assert backend == "streamlink"
    assert len(attempt_dirs) == 2
    assert attempt_dirs[0] != attempt_dirs[1]
    assert all(path.parent == tmp_path for path in attempt_dirs)
    assert result.output_paths == [attempt_dirs[1] / "stream.ts"]


def test_global_attempt_budget_never_exceeded(tmp_path, monkeypatch):
    import router
    from process_runner import MAX_TOTAL_ATTEMPTS, AttemptInfo

    route = RouteEntry(
        name="budget",
        patterns=[r"example\.com"],
        backends=["yt-dlp", "streamlink", "gallery-dl"],
        max_retries=5,
    )
    observed = []

    def fake_execute(backend_name, _url, output_dir, runner=None, max_attempts=None):
        del runner, output_dir
        observed.append((backend_name, max_attempts))
        attempts = [
            AttemptInfo(n, backend_name, "DOWNLOAD_FAILED", 1, 0.1, True, "fail")
            for n in range(1, max_attempts + 1)
        ]
        return BackendResult(status="DOWNLOAD_FAILED", attempts=attempts)

    monkeypatch.setattr(router, "execute_backend", fake_execute)
    monkeypatch.setattr(router, "probe_and_resolve_live", lambda *_args, **_kwargs: (None, None))

    result, _backend = download_with_fallback(
        "https://example.com/video",
        tmp_path,
        routes=[route],
    )

    total = len(result.attempts)
    assert total <= MAX_TOTAL_ATTEMPTS
    assert len(observed) == 2
    assert observed[0][1] == 5
    assert observed[1][1] == 1
    assert result.status == "RATE_LIMITED"


def test_fallback_succeeds_after_first_backend_fails(tmp_path, monkeypatch):
    import router

    route = RouteEntry(
        name="failover",
        patterns=[r"example\.com"],
        backends=["yt-dlp", "streamlink"],
        max_retries=1,
    )

    def fake_execute(backend_name, _url, output_dir, runner=None, max_attempts=None):
        del runner, max_attempts
        output_dir.mkdir(parents=True, exist_ok=True)
        if backend_name == "yt-dlp":
            return BackendResult(status="DOWNLOAD_FAILED")
        completed = output_dir / "stream.ts"
        completed.write_text("complete")
        return BackendResult(status="SUCCESS", output_paths=[completed])

    monkeypatch.setattr(router, "execute_backend", fake_execute)
    monkeypatch.setattr(router, "probe_and_resolve_live", lambda *_args, **_kwargs: (None, None))

    result, backend = download_with_fallback(
        "https://example.com/live",
        tmp_path,
        routes=[route],
    )
    assert result.status == "SUCCESS"
    assert backend == "streamlink"


def test_all_backends_fail_returns_last_error(tmp_path, monkeypatch):
    import router

    route = RouteEntry(
        name="all-fail",
        patterns=[r"example\.com"],
        backends=["yt-dlp", "streamlink"],
        max_retries=1,
    )

    def fake_execute(backend_name, _url, output_dir, runner=None, max_attempts=None):
        del runner, max_attempts, output_dir
        return BackendResult(status="DOWNLOAD_FAILED", stderr=f"{backend_name} failed")

    monkeypatch.setattr(router, "execute_backend", fake_execute)
    monkeypatch.setattr(router, "probe_and_resolve_live", lambda *_args, **_kwargs: (None, None))

    result, backend = download_with_fallback(
        "https://example.com/video",
        tmp_path,
        routes=[route],
    )
    assert result.status == "DOWNLOAD_FAILED"
    assert backend == "streamlink"
    assert "streamlink failed" in result.stderr
