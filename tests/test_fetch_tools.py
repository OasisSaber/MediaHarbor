from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FETCH = REPO_ROOT / "scripts" / "fetch_tools.py"

TOOLS_JSON = (
    '{"schema_version": 1, "tools": {"d": {"roles": ["t"], '
    '"platforms": {"windows-x64": "d/d.exe"}}}}'
)


def _setup_workspace(tmp: str) -> Path:
    root = Path(tmp)
    (root / "AGENT_READ_ME_FIRST.md").write_text("")
    (root / "download-tools").mkdir(parents=True, exist_ok=True)
    (root / "download-tools" / "tools.json").write_text(TOOLS_JSON)
    (root / "skill" / "untitled").mkdir(parents=True, exist_ok=True)
    (root / "skill" / "untitled" / "SKILL.md").write_text("---\ntitle: test\n---\n")
    return root


def _write_manifest(
    root: Path, base_url: str, archive: str, sha256: str, provides: list[str]
) -> None:
    manifest = {
        "schema_version": 1,
        "release_base_url": base_url,
        "tools": {
            "yt-dlp": {
                "kind": "zip",
                "version": "test-1.0",
                "archive": archive,
                "sha256": sha256,
                "license": "Unlicense",
                "upstream": "https://example.com/upstream",
                "provides": provides,
            },
            "yutto": {
                "kind": "pip",
                "version": "2.2.0",
                "package": "yutto",
                "license": "GPL-3.0",
                "upstream": "https://github.com/yutto-dev/yutto",
            },
        },
    }
    (root / "tools-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _make_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    # -S: skip site-packages so python-module tool detection (find_spec)
    # sees a clean interpreter regardless of what the developer installed.
    return subprocess.run(
        [sys.executable, "-S", str(FETCH), "--root", str(root), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_install_zip_tool():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        source = Path(tmp) / "src"
        source.mkdir()
        _make_zip(source / "tool.zip", {"yt-dlp/yt-dlp.exe": b"fake-binary"})
        sha = hashlib.sha256((source / "tool.zip").read_bytes()).hexdigest()
        _write_manifest(root, source.as_uri(), "tool.zip", sha, ["yt-dlp/yt-dlp.exe"])

        result = _run(root, "--tool", "yt-dlp")

        assert result.returncode == 0, result.stderr
        assert "installed" in result.stdout
        target = root / "download-tools" / "yt-dlp" / "yt-dlp.exe"
        assert target.is_file()
        assert target.read_bytes() == b"fake-binary"


def test_sha256_mismatch_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        source = Path(tmp) / "src"
        source.mkdir()
        _make_zip(source / "tool.zip", {"yt-dlp/yt-dlp.exe": b"fake-binary"})
        _write_manifest(root, source.as_uri(), "tool.zip", "0" * 64, ["yt-dlp/yt-dlp.exe"])

        result = _run(root, "--tool", "yt-dlp")

        assert result.returncode == 1
        assert "sha256 mismatch" in result.stdout
        assert not (root / "download-tools" / "yt-dlp" / "yt-dlp.exe").exists()


def test_zip_slip_member_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        source = Path(tmp) / "src"
        source.mkdir()
        _make_zip(source / "tool.zip", {"../evil.txt": b"evil"})
        sha = hashlib.sha256((source / "tool.zip").read_bytes()).hexdigest()
        _write_manifest(root, source.as_uri(), "tool.zip", sha, ["../evil.txt"])

        result = _run(root, "--tool", "yt-dlp")

        assert result.returncode == 1
        assert "unsafe member" in result.stdout or "escapes" in result.stdout
        assert not (Path(tmp) / "evil.txt").exists()


def test_installed_tool_is_skipped_without_force():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        tool_dir = root / "download-tools" / "yt-dlp"
        tool_dir.mkdir(parents=True)
        (tool_dir / "yt-dlp.exe").write_bytes(b"existing")
        _write_manifest(
            root, "https://invalid.invalid", "tool.zip", "0" * 64, ["yt-dlp/yt-dlp.exe"]
        )

        result = _run(root, "--tool", "yt-dlp")

        assert result.returncode == 0
        assert "already installed" in result.stdout


def test_check_reports_missing_and_ready():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        tool_dir = root / "download-tools" / "yt-dlp"
        tool_dir.mkdir(parents=True)
        (tool_dir / "yt-dlp.exe").write_bytes(b"x")
        _write_manifest(
            root, "https://invalid.invalid", "tool.zip", "0" * 64, ["yt-dlp/yt-dlp.exe"]
        )

        result = _run(root, "--check")

        assert result.returncode == 1
        assert "yt-dlp: ready" in result.stdout
        assert "yutto: missing" in result.stdout


def test_pip_tool_prints_guidance():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        _write_manifest(
            root, "https://invalid.invalid", "tool.zip", "0" * 64, ["yt-dlp/yt-dlp.exe"]
        )

        result = _run(root, "--tool", "yutto")

        assert result.returncode == 0
        assert "pip install yutto" in result.stdout


def test_verify_manifest_structural():
    with tempfile.TemporaryDirectory() as tmp:
        root = _setup_workspace(tmp)
        (root / "tools-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "release_base_url": "https://invalid.invalid/x",
                    "tools": {
                        "bad": {
                            "kind": "zip",
                            "version": "1",
                            "archive": "a.zip",
                            "sha256": "not-a-hash",
                            "license": "X",
                            "upstream": "u",
                            "provides": ["a.exe"],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        result = _run(root, "--verify-manifest")

        assert result.returncode == 1
        assert "invalid sha256" in result.stdout
