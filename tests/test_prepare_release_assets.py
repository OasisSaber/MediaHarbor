from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "prepare_release_assets.py"


def _manifest(root: Path, digest: str) -> None:
    (root / "tools-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_required": True,
                "release_base_url": "https://example.invalid/release",
                "tools": {
                    "tool": {
                        "kind": "zip",
                        "version": "1",
                        "archive": "tool.zip",
                        "sha256": digest,
                        "license": "MIT",
                        "upstream": "https://example.invalid/upstream",
                        "provides": ["tool/tool.exe"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _run(root: Path, asset_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--asset-dir",
            str(asset_dir),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_writes_matching_checksums(tmp_path: Path):
    assets = tmp_path / "assets"
    assets.mkdir()
    payload = assets / "tool.zip"
    payload.write_bytes(b"archive")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    _manifest(tmp_path, digest)

    result = _run(tmp_path, assets)

    assert result.returncode == 0, result.stdout
    assert (assets / "SHA256SUMS.txt").read_text(encoding="ascii") == (f"{digest}  tool.zip\n")


def test_rejects_checksum_mismatch(tmp_path: Path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "tool.zip").write_bytes(b"archive")
    _manifest(tmp_path, "0" * 64)

    result = _run(tmp_path, assets)

    assert result.returncode == 1
    assert "sha256 mismatch" in result.stdout
    assert not (assets / "SHA256SUMS.txt").exists()


def test_rejects_missing_asset(tmp_path: Path):
    assets = tmp_path / "assets"
    assets.mkdir()
    _manifest(tmp_path, "0" * 64)

    result = _run(tmp_path, assets, "--check-only")

    assert result.returncode == 1
    assert "missing asset" in result.stdout


def test_rejects_duplicate_archive_names(tmp_path: Path):
    assets = tmp_path / "assets"
    assets.mkdir()
    manifest = {
        "schema_version": 1,
        "release_required": True,
        "release_base_url": "https://example.invalid/release",
        "tools": {
            "one": {
                "kind": "zip",
                "version": "1",
                "archive": "shared.zip",
                "sha256": "0" * 64,
                "license": "MIT",
                "upstream": "u",
                "provides": ["one/tool.exe"],
            },
            "two": {
                "kind": "zip",
                "version": "1",
                "archive": "shared.zip",
                "sha256": "1" * 64,
                "license": "MIT",
                "upstream": "u",
                "provides": ["two/tool.exe"],
            },
        },
    }
    (tmp_path / "tools-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = _run(tmp_path, assets, "--check-only")

    assert result.returncode == 1
    assert "duplicate archive" in result.stdout


def test_rejects_windows_invalid_archive_name(tmp_path: Path):
    assets = tmp_path / "assets"
    assets.mkdir()
    manifest = {
        "schema_version": 1,
        "release_required": True,
        "release_base_url": "https://example.invalid/release",
        "tools": {
            "bad": {
                "kind": "zip",
                "version": "1",
                "archive": r"dir\tool.zip",
                "sha256": "0" * 64,
                "license": "MIT",
                "upstream": "u",
                "provides": ["tool/tool.exe"],
            }
        },
    }
    (tmp_path / "tools-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = _run(tmp_path, assets, "--check-only")

    assert result.returncode == 1
    assert "invalid archive name" in result.stdout
