#!/usr/bin/env python3
"""Fetch and verify Untitled download tools.

ZIP-backed tools are published in the GitHub Release declared by
``tools-manifest.json``. Python-module tools are installed explicitly into the
active interpreter and are never downloaded implicitly by Untitled.

Usage:
    python scripts/fetch_tools.py [--tool NAME] [--force] [--root DIR]
    python scripts/fetch_tools.py --check [--root DIR]
    python scripts/fetch_tools.py --check-updates [--root DIR]
    python scripts/fetch_tools.py --verify-manifest [--root DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, urlunsplit

DEFAULT_MANIFEST = "tools-manifest.json"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = "download-tools"
CHECKSUMS_ASSET = "SHA256SUMS.txt"
NETWORK_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 300
USER_AGENT = "Untitled-tool-fetcher/1"

REQUIRED_FIELDS = {"kind", "version", "license", "upstream"}
ZIP_FIELDS = {"archive", "sha256", "provides"}
PIP_FIELDS = {"package"}
HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
MODULE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
WINDOWS_ILLEGAL_PATH_CHARS = set('<>:"|?*')


class FetchError(RuntimeError):
    """Expected, user-actionable tool distribution failure."""


def _safe_public_url(url: str) -> str:
    """Return a diagnostic URL without query parameters or fragments."""
    try:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except ValueError:
        return "<invalid-url>"


def _request(url: str, *, timeout: int, range_probe: bool = False):
    headers = {"User-Agent": USER_AGENT}
    if range_probe:
        headers["Range"] = "bytes=0-0"
    request = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(request, timeout=timeout)


def load_manifest(root: Path) -> dict:
    path = root / DEFAULT_MANIFEST
    if not path.is_file():
        raise FetchError(f"manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FetchError(f"invalid manifest JSON: {error}") from error

    if data.get("schema_version") != 1:
        raise FetchError(f"unsupported manifest schema: {data.get('schema_version')}")
    if not isinstance(data.get("release_base_url"), str) or not data["release_base_url"].strip():
        raise FetchError("manifest missing release_base_url")
    if not isinstance(data.get("release_required"), bool):
        raise FetchError("manifest missing boolean release_required")

    tools = data.get("tools")
    if not isinstance(tools, dict) or not tools:
        raise FetchError("manifest missing tools")
    for name, entry in tools.items():
        validate_entry(name, entry)
    _validate_manifest_inventory(tools)
    return data


def _validate_archive_member_path(member: str, *, context: str) -> PurePosixPath:
    """Validate a ZIP/manifest member consistently on every host OS."""
    if not isinstance(member, str) or not member:
        raise FetchError(f"{context}: path must be a non-empty string")
    if "\\" in member:
        raise FetchError(f"{context}: backslashes are not allowed: {member}")
    if member.startswith("/") or member.endswith("/") or "//" in member:
        raise FetchError(f"{context}: path must be a normalized relative file: {member}")
    components = member.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise FetchError(f"{context}: unsafe path: {member}")
    if any(any(ord(char) < 32 for char in component) for component in components):
        raise FetchError(f"{context}: control characters are not allowed: {member!r}")
    has_illegal = any(
        any(char in WINDOWS_ILLEGAL_PATH_CHARS for char in component) for component in components
    )
    if has_illegal:
        raise FetchError(f"{context}: Windows-illegal character in path: {member}")
    path = PurePosixPath(member)
    if path.is_absolute() or not path.parts:
        raise FetchError(f"{context}: unsafe path: {member}")
    return path


def _validate_manifest_inventory(tools: dict[str, dict]) -> None:
    """Reject cross-tool archive and destination collisions."""
    archives: dict[str, str] = {}
    destinations: dict[str, str] = {}
    for name, entry in tools.items():
        if entry["kind"] != "zip":
            continue
        archive = entry["archive"]
        previous_archive = archives.get(archive)
        if previous_archive is not None:
            raise FetchError(
                f"duplicate archive '{archive}' used by tools '{previous_archive}' and '{name}'"
            )
        archives[archive] = name
        for member in entry["provides"]:
            previous_tool = destinations.get(member)
            if previous_tool is not None:
                raise FetchError(
                    f"duplicate destination '{member}' used by tools '{previous_tool}' and '{name}'"
                )
            destinations[member] = name


def validate_entry(name: str, entry: dict) -> None:
    if not isinstance(name, str) or not name:
        raise FetchError("tool name must be a non-empty string")
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
        if not isinstance(sha, str) or not HEX_64_RE.fullmatch(sha):
            raise FetchError(f"tool '{name}' invalid sha256")
        archive = entry["archive"]
        if not isinstance(archive, str) or not archive:
            raise FetchError(f"tool '{name}' archive must be a plain file name")
        archive_path = _validate_archive_member_path(archive, context=f"tool '{name}' archive")
        if len(archive_path.parts) != 1:
            raise FetchError(f"tool '{name}' archive must be a plain file name")

        provides = entry["provides"]
        if not isinstance(provides, list) or not provides:
            raise FetchError(f"tool '{name}' provides must be a non-empty list")
        seen: set[str] = set()
        for member in provides:
            _validate_archive_member_path(member, context=f"tool '{name}' provides")
            if member in seen:
                raise FetchError(f"tool '{name}' provides duplicate path: {member}")
            seen.add(member)
    elif kind == "pip":
        missing = PIP_FIELDS - set(entry)
        if missing:
            raise FetchError(f"pip tool '{name}' missing fields: {sorted(missing)}")
        package = entry["package"]
        if not isinstance(package, str) or not package.strip():
            raise FetchError(f"pip tool '{name}' package must be a non-empty string")
        module = entry.get("module") or package.replace("-", "_")
        if not isinstance(module, str) or not MODULE_NAME_RE.fullmatch(module):
            raise FetchError(f"pip tool '{name}' invalid module name: {module!r}")
    else:
        raise FetchError(f"tool '{name}' unknown kind '{kind}'")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_asset(base_url: str, archive: str, destination: Path) -> None:
    url = f"{base_url.rstrip('/')}/{archive}"
    try:
        with _request(url, timeout=DOWNLOAD_TIMEOUT) as response:
            with destination.open("wb") as handle:
                shutil.copyfileobj(response, handle)
    except urllib.error.HTTPError as error:
        raise FetchError(
            f"asset download failed with HTTP {error.code}: {_safe_public_url(url)}"
        ) from error
    except urllib.error.URLError as error:
        raise FetchError(
            f"asset download failed: {_safe_public_url(url)} ({error.reason})"
        ) from error
    except OSError as error:
        raise FetchError(f"cannot write downloaded asset: {destination} ({error})") from error


def extract_zip(archive_path: Path, staging_root: Path, provides: list[str]) -> None:
    """Extract only declared files into a private staging directory."""
    staging_root.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            name_counts = Counter(info.filename for info in archive.infolist())
            for member in provides:
                relative = _validate_archive_member_path(member, context="manifest provides")
                count = name_counts.get(member, 0)
                if count == 0:
                    raise FetchError(f"declared member missing from archive: {member}")
                if count != 1:
                    raise FetchError(f"declared member appears multiple times in archive: {member}")
                destination = (staging_root / Path(*relative.parts)).resolve()
                try:
                    destination.relative_to(staging_root.resolve())
                except ValueError as error:
                    raise FetchError(f"member escapes staging directory: {member}") from error
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as handle:
                    shutil.copyfileobj(source, handle)
    except zipfile.BadZipFile as error:
        raise FetchError(f"invalid zip archive: {archive_path.name}") from error


def _install_staged_files(staging_root: Path, target_root: Path, provides: list[str]) -> None:
    """Install a complete staged tool set with rollback on partial failure."""
    transaction_id = uuid.uuid4().hex[:12]
    backup_root = target_root.parent / f".tool-backup-{transaction_id}"
    installed: list[Path] = []
    backed_up: list[tuple[Path, Path]] = []
    target_root.mkdir(parents=True, exist_ok=True)
    preserve_backup = False

    try:
        for member in provides:
            relative = _validate_archive_member_path(member, context="install member")
            source = (staging_root / Path(*relative.parts)).resolve()
            source.relative_to(staging_root.resolve())
            if not source.is_file():
                raise FetchError(f"staged file missing: {member}")

            destination = (target_root / Path(*relative.parts)).resolve()
            destination.relative_to(target_root.resolve())
            destination.parent.mkdir(parents=True, exist_ok=True)

            if destination.exists():
                backup = backup_root / Path(*relative.parts)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(backup))
                backed_up.append((destination, backup))

            os.replace(source, destination)
            installed.append(destination)
    except Exception as error:
        rollback_errors: list[str] = []
        for destination in reversed(installed):
            try:
                destination.unlink(missing_ok=True)
            except OSError as rollback_error:
                rollback_errors.append(f"cannot remove {destination}: {rollback_error}")
        for destination, backup in reversed(backed_up):
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(backup), str(destination))
            except OSError as rollback_error:
                rollback_errors.append(f"cannot restore {destination}: {rollback_error}")

        if rollback_errors:
            preserve_backup = True
            detail = (
                "; rollback problems: "
                + " | ".join(rollback_errors)
                + f"; backup preserved at {backup_root}"
            )
        else:
            detail = ""
        if isinstance(error, FetchError):
            raise FetchError(f"{error}{detail}") from error
        raise FetchError(f"tool installation failed: {error}{detail}") from error
    finally:
        if not preserve_backup:
            shutil.rmtree(backup_root, ignore_errors=True)


def tool_installed(root: Path, entry: dict) -> bool:
    if entry["kind"] == "pip":
        module = entry.get("module") or entry["package"].replace("-", "_")
        return importlib.util.find_spec(module) is not None
    return all((root / TOOLS_DIR / member).is_file() for member in entry["provides"])


def fetch_tool(root: Path, name: str, entry: dict, force: bool = False) -> str:
    if entry["kind"] == "pip":
        return (
            f"tool '{name}' is Python-module backed; install it into the current "
            f"interpreter with `{sys.executable} -m pip install {entry['package']}`; "
            "then rerun `python untitled.py check-tools`"
        )
    if tool_installed(root, entry) and not force:
        return f"tool '{name}' already installed (use --force to reinstall)"

    manifest = load_manifest(root)
    base_url = manifest["release_base_url"]
    with tempfile.TemporaryDirectory(prefix="untitled-download-") as download_tmp:
        archive_path = Path(download_tmp) / entry["archive"]
        download_asset(base_url, entry["archive"], archive_path)
        actual = sha256_of(archive_path)
        if actual != entry["sha256"]:
            raise FetchError(
                f"sha256 mismatch for {name}: expected {entry['sha256']}, got {actual}"
            )

        with tempfile.TemporaryDirectory(prefix=".tool-staging-", dir=root) as staging_tmp:
            staging_root = Path(staging_tmp)
            extract_zip(archive_path, staging_root, entry["provides"])
            _install_staged_files(staging_root, root / TOOLS_DIR, entry["provides"])

    return f"tool '{name}' installed ({entry['version']})"


def run_check(root: Path) -> dict[str, str]:
    manifest = load_manifest(root)
    return {
        name: "ready" if tool_installed(root, entry) else "missing"
        for name, entry in manifest["tools"].items()
    }


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
        url = f"https://api.github.com/{endpoint}"
        try:
            with _request(url, timeout=NETWORK_TIMEOUT) as response:
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
        except (urllib.error.URLError, json.JSONDecodeError, UnicodeError) as error:
            reports.append({"tool": name, "error": str(error)})
    return reports


def _parse_checksum_file(raw: str) -> tuple[dict[str, str], list[str]]:
    checksums: dict[str, str] = {}
    problems: list[str] = []
    for line_number, raw_line in enumerate(raw.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            problems.append(f"SHA256SUMS line {line_number}: invalid format")
            continue
        digest, filename = parts
        filename = filename.lstrip("*")
        if not HEX_64_RE.fullmatch(digest):
            problems.append(f"SHA256SUMS line {line_number}: invalid sha256")
            continue
        if Path(filename).name != filename:
            problems.append(f"SHA256SUMS line {line_number}: filename must be plain")
            continue
        previous = checksums.get(filename)
        if previous is not None and previous != digest:
            problems.append(f"SHA256SUMS: conflicting duplicate for {filename}")
            continue
        checksums[filename] = digest
    return checksums, problems


def _read_required_checksums(base_url: str) -> str:
    url = f"{base_url.rstrip('/')}/{CHECKSUMS_ASSET}"
    try:
        with _request(url, timeout=NETWORK_TIMEOUT) as response:
            return response.read().decode("ascii", errors="strict")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise FetchError(
                f"required release checksum file not found (404): {_safe_public_url(url)}"
            ) from error
        raise FetchError(
            f"release checksum request failed with HTTP {error.code}: {_safe_public_url(url)}"
        ) from error
    except urllib.error.URLError as error:
        raise FetchError(
            f"release checksum request failed: {_safe_public_url(url)} ({error.reason})"
        ) from error
    except UnicodeError as error:
        raise FetchError("SHA256SUMS.txt is not valid ASCII") from error


def _probe_required_asset(base_url: str, archive: str) -> None:
    url = f"{base_url.rstrip('/')}/{archive}"
    try:
        with _request(url, timeout=NETWORK_TIMEOUT, range_probe=True) as response:
            response.read(1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise FetchError(f"required release asset not found (404): {archive}") from error
        raise FetchError(f"release asset probe failed with HTTP {error.code}: {archive}") from error
    except urllib.error.URLError as error:
        raise FetchError(f"release asset probe failed for {archive}: {error.reason}") from error


def verify_manifest(root: Path) -> list[str]:
    """Validate manifest structure and, when required, the published release."""
    manifest = load_manifest(root)
    if not manifest["release_required"]:
        return []

    problems: list[str] = []
    base_url = manifest["release_base_url"]
    try:
        sums = _read_required_checksums(base_url)
    except FetchError as error:
        return [str(error)]

    expected, parse_problems = _parse_checksum_file(sums)
    problems.extend(parse_problems)

    for name, entry in manifest["tools"].items():
        if entry["kind"] != "zip":
            continue
        archive = entry["archive"]
        published = expected.get(archive)
        if published is None:
            problems.append(f"{name}: archive {archive} missing from SHA256SUMS")
            continue
        if published != entry["sha256"]:
            problems.append(f"{name}: sha256 differs from published release")
            continue
        try:
            _probe_required_asset(base_url, archive)
        except FetchError as error:
            problems.append(f"{name}: {error}")

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
        "--verify-manifest",
        action="store_true",
        help="Validate manifest and require published assets when release_required=true",
    )
    args = parser.parse_args(argv)

    try:
        if args.verify_manifest:
            manifest = load_manifest(args.root)
            problems = verify_manifest(args.root)
            for problem in problems:
                print(f"ERROR: {problem}")
            if not manifest["release_required"] and not problems:
                print(
                    "WARNING: release_required=false; remote Release and assets were not verified"
                )
            return 1 if problems else 0

        if args.check_updates:
            for report in check_updates(args.root):
                print(json.dumps(report, ensure_ascii=False))
            return 0

        if args.check:
            status = run_check(args.root)
            for name, state in status.items():
                print(f"{name}: {state}")
            return 0 if all(state == "ready" for state in status.values()) else 1

        manifest = load_manifest(args.root)
        if args.tool and args.tool not in manifest["tools"]:
            raise FetchError(f"unknown tool: {args.tool}")
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
            sys.path.insert(0, str((args.root / "skill" / "untitled" / "scripts").resolve()))
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
