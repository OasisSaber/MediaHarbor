#!/usr/bin/env python3
"""Fetch Untitled download tools from this repository's GitHub Release.

Tools are distributed as zip assets of the Untitled release
``tools-windows-x64-v1`` (see ``tools-manifest.json``). Each zip contains
files laid out relative to the ``download-tools/`` directory, so extraction
places them directly (e.g. ``yt-dlp/yt-dlp.exe``).

Usage:
    python scripts/fetch_tools.py [--tool NAME] [--force] [--root DIR]
    python scripts/fetch_tools.py --check [--root DIR]
    python scripts/fetch_tools.py --check-updates
    python scripts/fetch_tools.py --verify-manifest [--root DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_MANIFEST = "tools-manifest.json"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = "download-tools"

REQUIRED_FIELDS = {"kind", "version", "license", "upstream"}
ZIP_FIELDS = {"archive", "sha256", "provides"}
PIP_FIELDS = {"package"}


class FetchError(RuntimeError):
    pass


def load_manifest(root: Path) -> dict:
    path = root / DEFAULT_MANIFEST
    if not path.is_file():
        raise FetchError(f"manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise FetchError(f"invalid manifest JSON: {error}") from error
    if data.get("schema_version") != 1:
        raise FetchError(f"unsupported manifest schema: {data.get('schema_version')}")
    if not data.get("release_base_url"):
        raise FetchError("manifest missing release_base_url")
    tools = data.get("tools")
    if not isinstance(tools, dict) or not tools:
        raise FetchError("manifest missing tools")
    for name, entry in tools.items():
        validate_entry(name, entry)
    return data


def validate_entry(name: str, entry: dict) -> None:
    if not isinstance(entry, dict):
        raise FetchError(f"tool '{name}' entry must be an object")
    missing = REQUIRED_FIELDS - set(entry)
    if missing:
        raise FetchError(f"tool '{name}' missing fields: {sorted(missing)}")
    kind = entry["kind"]
    if kind == "zip":
        missing = ZIP_FIELDS - set(entry)
        if missing:
            raise FetchError(f"zip tool '{name}' missing fields: {sorted(missing)}")
        sha = entry["sha256"]
        if (
            not isinstance(sha, str)
            or len(sha) != 64
            or any(c not in "0123456789abcdef" for c in sha)
        ):
            raise FetchError(f"tool '{name}' invalid sha256")
        if (
            not isinstance(entry["archive"], str)
            or "/" in entry["archive"]
            or "\\" in entry["archive"]
        ):
            raise FetchError(f"tool '{name}' archive must be a plain file name")
        provides = entry["provides"]
        if not isinstance(provides, list) or not provides:
            raise FetchError(f"tool '{name}' provides must be a non-empty list")
    elif kind == "pip":
        missing = PIP_FIELDS - set(entry)
        if missing:
            raise FetchError(f"pip tool '{name}' missing fields: {sorted(missing)}")
    else:
        raise FetchError(f"tool '{name}' unknown kind '{kind}'")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_asset(base_url: str, archive: str, destination: Path) -> None:
    url = f"{base_url.rstrip('/')}/{archive}"
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            with open(destination, "wb") as handle:
                shutil.copyfileobj(response, handle)
    except urllib.error.HTTPError as error:
        raise FetchError(f"download failed ({error.code}) for {url}") from error
    except urllib.error.URLError as error:
        raise FetchError(f"download failed for {url}: {error.reason}") from error


def extract_zip(archive_path: Path, target_root: Path, provides: list[str]) -> None:
    """Extract only the declared entries, guarding against zip-slip."""
    target_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in provides:
            normalized = Path(member)
            if normalized.is_absolute() or ".." in normalized.parts:
                raise FetchError(f"unsafe member path in manifest: {member}")
            destination = (target_root / normalized).resolve()
            try:
                destination.relative_to(target_root.resolve())
            except ValueError as error:
                raise FetchError(f"member escapes target directory: {member}") from error
            source = archive.open(member)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source, open(destination, "wb") as handle:
                shutil.copyfileobj(source, handle)


def tool_installed(root: Path, entry: dict) -> bool:
    if entry["kind"] == "pip":
        module = entry.get("module") or entry["package"].replace("-", "_")
        return importlib.util.find_spec(module) is not None
    for member in entry["provides"]:
        if not (root / TOOLS_DIR / member).is_file():
            return False
    return True


def fetch_tool(root: Path, name: str, entry: dict, force: bool = False) -> str:
    if entry["kind"] == "pip":
        return (
            f"tool '{name}' is Python-module backed; install it into the current "
            f"interpreter with `{sys.executable} -m pip install {entry['package']}`; "
            f"then rerun `python untitled.py check-tools`"
        )
    if tool_installed(root, entry) and not force:
        return f"tool '{name}' already installed (use --force to reinstall)"
    base_url = load_manifest(root)["release_base_url"]
    with tempfile.TemporaryDirectory() as tmp:
        archive_path = Path(tmp) / entry["archive"]
        download_asset(base_url, entry["archive"], archive_path)
        actual = sha256_of(archive_path)
        if actual != entry["sha256"]:
            raise FetchError(
                f"sha256 mismatch for {name}: expected {entry['sha256']}, got {actual}"
            )
        extract_zip(archive_path, root / TOOLS_DIR, entry["provides"])
    return f"tool '{name}' installed ({entry['version']})"


def run_check(root: Path) -> dict:
    manifest = load_manifest(root)
    result: dict[str, str] = {}
    for name, entry in manifest["tools"].items():
        result[name] = "ready" if tool_installed(root, entry) else "missing"
    return result


def _normalize_version(raw: str | None) -> str:
    if not raw:
        return ""
    return raw.strip().lstrip("v").split(" ")[0].split("(")[0].strip()


def check_updates(root: Path) -> list[dict]:
    """Query upstream latest tags (best-effort, no authentication)."""
    manifest = load_manifest(root)
    reports = []
    api_map = {
        "yt-dlp": "repos/yt-dlp/yt-dlp/releases/latest",
        "ffmpeg": None,
        "n-m3u8dl-re": "repos/nilaoda/N_m3u8DL-RE/releases/latest",
        "yutto": "repos/yutto-dev/yutto/releases/latest",
        "streamlink": "repos/streamlink/streamlink/releases/latest",
        "gallery-dl": "repos/mikf/gallery-dl/releases/latest",
    }
    for name, entry in manifest["tools"].items():
        endpoint = api_map.get(name)
        if not endpoint:
            reports.append({"tool": name, "upstream": "manual review required"})
            continue
        try:
            with urllib.request.urlopen(
                f"https://api.github.com/{endpoint}", timeout=30
            ) as response:
                latest = json.loads(response.read().decode("utf-8")).get("tag_name")
            reports.append(
                {
                    "tool": name,
                    "manifest_version": entry["version"],
                    "upstream_latest": latest,
                    "update_available": _normalize_version(latest)
                    != _normalize_version(entry["version"]),
                }
            )
        except (urllib.error.URLError, json.JSONDecodeError) as error:
            reports.append({"tool": name, "error": str(error)})
    return reports


def verify_manifest(root: Path) -> list[str]:
    """Structural validation; cross-check SHA256SUMS when the release exists."""
    manifest = load_manifest(root)
    problems: list[str] = []
    base_url = manifest["release_base_url"]
    try:
        with urllib.request.urlopen(
            f"{base_url.rstrip('/')}/SHA256SUMS.txt", timeout=30
        ) as response:
            sums = response.read().decode("ascii", errors="replace")
    except urllib.error.HTTPError:
        return problems  # release not published yet; structural check only
    except urllib.error.URLError:
        return problems
    expected: dict[str, str] = {}
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2:
            expected[parts[1]] = parts[0]
    for name, entry in manifest["tools"].items():
        if entry["kind"] != "zip":
            continue
        published = expected.get(entry["archive"])
        if published is None:
            problems.append(f"{name}: archive {entry['archive']} missing from SHA256SUMS")
        elif published != entry["sha256"]:
            problems.append(f"{name}: sha256 differs from published release")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Untitled tools from the project release")
    parser.add_argument("--tool", help="Only fetch this tool (default: all missing zip tools)")
    parser.add_argument("--force", action="store_true", help="Reinstall even if present")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Untitled root")
    parser.add_argument("--check", action="store_true", help="Report tool status, do not download")
    parser.add_argument(
        "--check-updates", action="store_true", help="Query upstream latest versions"
    )
    parser.add_argument(
        "--verify-manifest", action="store_true", help="Validate manifest and release sums"
    )
    args = parser.parse_args(argv)

    try:
        if args.verify_manifest:
            problems = verify_manifest(args.root)
            for problem in problems:
                print(f"ERROR: {problem}")
            return 1 if problems else 0
        if args.check_updates:
            for report in check_updates(args.root):
                print(json.dumps(report, ensure_ascii=False))
            return 0
        if args.check:
            status = run_check(args.root)
            for name, state in status.items():
                print(f"{name}: {state}")
            return 0 if all(s == "ready" for s in status.values()) else 1

        manifest = load_manifest(args.root)
        targets = (
            {args.tool: manifest["tools"][args.tool]}
            if args.tool
            else {
                name: entry for name, entry in manifest["tools"].items() if entry["kind"] == "zip"
            }
        )
        failed = False
        for name, entry in targets.items():
            try:
                print(fetch_tool(args.root, name, entry, force=args.force))
            except FetchError as error:
                print(f"ERROR: {error}")
                failed = True
        if not args.tool and not failed:
            import sys as _sys

            _sys.path.insert(0, str((args.root / "skill" / "untitled" / "scripts").resolve()))
            from _common import check_tools, load_registry

            registry = load_registry(args.root)
            result = check_tools(registry)
            print(f"check_tools: {result.status}")
        return 1 if failed else 0
    except FetchError as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
