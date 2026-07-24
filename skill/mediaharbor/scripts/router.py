from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from _common import find_project_root
from process_runner import BUDGET_EXHAUSTED, MAX_TOTAL_ATTEMPTS, ProcessResult, ProcessRunner

ROUTING_TABLE_FILE = "routing.json"


@dataclass
class RouteEntry:
    name: str
    patterns: list[str] = field(default_factory=list)
    backends: list[str] = field(default_factory=list)
    max_retries: int = 2
    drm_stop: bool = True


_VALID_BACKEND_NAMES = {"yt-dlp", "yutto", "streamlink", "n-m3u8dl-re", "gallery-dl"}


def _validate_routing_table(data: dict) -> list[RouteEntry]:
    schema = data.get("schema_version", 0)
    if schema != 1:
        raise ValueError(f"Unsupported routing schema: {schema}")
    routes_raw = data.get("routes")
    if not isinstance(routes_raw, list):
        raise ValueError("'routes' must be a list")
    if not routes_raw:
        raise ValueError("Empty routing table")
    result = []
    seen = set()
    for entry in routes_raw:
        name = entry.get("name", "")
        if not name:
            raise ValueError("Route entry missing name")
        if name in seen:
            raise ValueError(f"Duplicate route name: {name}")
        seen.add(name)
        patterns = entry.get("patterns", [])
        if not patterns:
            raise ValueError(f"Route '{name}' has no patterns")
        for p in patterns:
            try:
                re.compile(p)
            except re.error as e:
                raise ValueError(f"Route '{name}' invalid regex '{p}': {e}")
        backends = entry.get("backends", [])
        if not backends:
            raise ValueError(f"Route '{name}' has no backends")
        for b in backends:
            if b not in _VALID_BACKEND_NAMES:
                raise ValueError(f"Route '{name}' unknown backend: {b}")
        max_r = entry.get("max_retries", 2)
        if not (1 <= max_r <= 5):
            raise ValueError(f"Route '{name}' max_retries out of range 1-5: {max_r}")
        result.append(
            RouteEntry(
                name=name,
                patterns=patterns,
                backends=backends,
                max_retries=max_r,
                drm_stop=entry.get("drm_stop", True),
            )
        )
    return result


def load_routing_table(start: Path | None = None, safe_fallback: bool = False) -> list[RouteEntry]:
    root = find_project_root(start)
    routing_path = root / "download-tools" / ROUTING_TABLE_FILE
    if not routing_path.is_file():
        if safe_fallback:
            print("routing.json not found, using builtin fallback", file=sys.stderr)
            return _builtin_routes()
        raise ValueError("routing.json not found")
    data = json.loads(routing_path.read_text(encoding="utf-8"))
    try:
        return _validate_routing_table(data)
    except (ValueError, KeyError) as e:
        if safe_fallback:
            print(
                f"Warning: invalid routing.json ({e}), using builtin fallback",
                file=sys.stderr,
            )
            return _builtin_routes()
        raise ValueError(f"Invalid routing.json: {e}") from e


def _builtin_routes() -> list[RouteEntry]:
    return [
        RouteEntry(
            name="bilibili",
            patterns=[r"bilibili\.com", r"b23\.tv"],
            backends=["yt-dlp", "yutto"],
        ),
        RouteEntry(
            name="hls-dash",
            patterns=[r"\.m3u8($|\?)", r"\.mpd($|\?)"],
            backends=["yt-dlp", "n-m3u8dl-re"],
        ),
        RouteEntry(
            name="social",
            patterns=[
                r"(twitter|x)\.com/",
                r"instagram\.com/",
                r"reddit\.com/",
                r"tumblr\.com/",
                r"pixiv\.net/",
            ],
            backends=["gallery-dl", "yt-dlp"],
        ),
        RouteEntry(
            name="vod",
            patterns=[r"^https?://"],
            backends=["yt-dlp"],
        ),
    ]


def match_route(url: str, routes: list[RouteEntry] | None = None) -> RouteEntry | None:
    if routes is None:
        routes = load_routing_table(safe_fallback=False)
    for route in routes:
        for pattern in route.patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return route
    return None


def probe_and_resolve_live(
    url: str, runner: ProcessRunner | None = None
) -> tuple[RouteEntry | None, dict | None]:
    from ytdlp_adapter import parse_probe_json, probe_url

    result = probe_url(url, runner=runner)
    if result.status != "SUCCESS":
        return None, None
    info = parse_probe_json(result.stdout)
    if not info:
        return None, None
    is_live = info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming")
    if is_live:
        live_route = RouteEntry(
            name="live",
            patterns=[r"^https?://"],
            backends=["streamlink", "yt-dlp"],
        )
        return live_route, info
    return None, info


def execute_backend(
    backend_name: str,
    url: str,
    output_dir: Path,
    runner: ProcessRunner | None = None,
) -> ProcessResult:
    if runner is None:
        runner = ProcessRunner()
    if backend_name == "yt-dlp":
        from ytdlp_adapter import download_url

        return download_url(url, output_dir, runner=runner)
    if backend_name == "yutto":
        from backends.yutto import run_yutto

        return run_yutto(url, output_dir, runner=runner)
    if backend_name == "streamlink":
        from backends.streamlink import run_streamlink

        return run_streamlink(url, output_dir, runner=runner)
    if backend_name == "n-m3u8dl-re":
        from backends.n_m3u8dl_re import run_n_m3u8dl_re

        return run_n_m3u8dl_re(url, output_dir, runner=runner)
    if backend_name == "gallery-dl":
        from backends.gallery_dl import run_gallery_dl

        return run_gallery_dl(url, output_dir, runner=runner)
    return ProcessResult(
        returncode=-1,
        stdout="",
        stderr=f"Unknown backend: {backend_name}",
        status="UNSUPPORTED_URL",
    )


def download_with_fallback(
    url: str,
    output_dir: Path,
    routes: list[RouteEntry] | None = None,
    max_backends: int = 3,
    runner: ProcessRunner | None = None,
) -> tuple[ProcessResult, str | None]:
    if routes is None:
        try:
            routes = load_routing_table(safe_fallback=False)
        except ValueError:
            return (
                ProcessResult(
                    returncode=-1,
                    stdout="",
                    stderr="routing.json not found or invalid",
                    status="CONFIG_ERROR",
                ),
                None,
            )

    route = match_route(url, routes)
    if route is None:
        return (
            ProcessResult(
                returncode=-1,
                stdout="",
                stderr=f"No route for: {url}",
                status="UNSUPPORTED_URL",
            ),
            None,
        )

    live_route, _probe_info = probe_and_resolve_live(url, runner=runner)
    if live_route is not None:
        route = live_route

    backends = route.backends[:max_backends]
    all_attempts = []
    last_result = None
    total_attempts = 0

    for backend_name in backends:
        remaining = MAX_TOTAL_ATTEMPTS - total_attempts
        if remaining <= 0:
            last_result = ProcessResult(
                returncode=-1,
                stdout="",
                stderr="Total attempt limit exceeded",
                status=BUDGET_EXHAUSTED,
                attempts=list(all_attempts),
            )
            break
        if runner is None:
            runner = ProcessRunner()
        saved_retries = runner.max_retries
        runner.max_retries = min(route.max_retries, remaining)
        result = execute_backend(backend_name, url, output_dir, runner=runner)
        runner.max_retries = saved_retries
        all_attempts.extend(result.attempts)
        total_attempts += len(result.attempts)
        last_result = result

        if result.status == "SUCCESS":
            result.attempts = all_attempts
            return result, backend_name

        if result.status in ("DRM_DETECTED", "AUTH_REQUIRED", "GEO_RESTRICTED"):
            result.attempts = all_attempts
            return result, backend_name

    if last_result:
        last_result.attempts = all_attempts
    return last_result, (backends[-1] if backends else None)
