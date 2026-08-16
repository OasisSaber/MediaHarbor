#!/usr/bin/env python3
"""Validate local BagItUp release assets and write SHA256SUMS.txt.

This script never uploads or deletes a GitHub Release. It prepares a directory
for the separately authorized human release step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = "tools-manifest.json"
CHECKSUMS_ASSET = "SHA256SUMS.txt"
HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_ILLEGAL_FILE_CHARS = set('<>:"/\\|?*')


class PreparationError(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_archive_name(name: str, archive: object) -> str:
    if not isinstance(archive, str) or not archive:
        raise PreparationError(f"{name}: invalid archive name")
    if any(char in WINDOWS_ILLEGAL_FILE_CHARS for char in archive):
        raise PreparationError(f"{name}: invalid archive name")
    path = PurePosixPath(archive)
    if path.is_absolute() or len(path.parts) != 1 or path.name != archive:
        raise PreparationError(f"{name}: invalid archive name")
    return archive


def load_zip_entries(root: Path) -> list[tuple[str, str]]:
    manifest_path = root / DEFAULT_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PreparationError(f"cannot read manifest: {error}") from error

    tools = manifest.get("tools")
    if not isinstance(tools, dict):
        raise PreparationError("manifest tools must be an object")

    entries: list[tuple[str, str]] = []
    seen_archives: set[str] = set()
    for name, entry in tools.items():
        if not isinstance(entry, dict) or entry.get("kind") != "zip":
            continue
        archive = _validate_archive_name(name, entry.get("archive"))
        expected = entry.get("sha256")
        if not isinstance(expected, str) or not HEX_64_RE.fullmatch(expected):
            raise PreparationError(f"{name}: invalid manifest sha256")
        if archive in seen_archives:
            raise PreparationError(f"duplicate archive in manifest: {archive}")
        seen_archives.add(archive)
        entries.append((archive, expected))
    if not entries:
        raise PreparationError("manifest contains no zip-backed tools")
    return entries


def prepare(root: Path, asset_dir: Path, *, write: bool) -> list[str]:
    problems: list[str] = []
    sums: list[tuple[str, str]] = []
    for archive, expected in load_zip_entries(root):
        path = asset_dir / archive
        if not path.is_file():
            problems.append(f"missing asset: {archive}")
            continue
        actual = sha256_of(path)
        sums.append((archive, actual))
        if actual != expected:
            problems.append(f"sha256 mismatch for {archive}: expected {expected}, got {actual}")

    if write and not problems:
        output = asset_dir / CHECKSUMS_ASSET
        text = "".join(f"{digest}  {archive}\n" for archive, digest in sorted(sums))
        output.write_text(text, encoding="ascii", newline="\n")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate local release assets and prepare SHA256SUMS.txt"
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root")
    parser.add_argument("--asset-dir", type=Path, required=True, help="directory containing zips")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="validate without creating SHA256SUMS.txt",
    )
    args = parser.parse_args(argv)

    try:
        problems = prepare(args.root, args.asset_dir, write=not args.check_only)
    except PreparationError as error:
        print(f"ERROR: {error}")
        return 1

    for problem in problems:
        print(f"ERROR: {problem}")
    if problems:
        return 1

    action = "validated" if args.check_only else "validated and wrote SHA256SUMS.txt"
    print(f"release assets {action}: {args.asset_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
