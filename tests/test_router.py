from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "skill" / "mediaharbor" / "scripts")
)
from process_runner import BackendResult
from router import (
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
