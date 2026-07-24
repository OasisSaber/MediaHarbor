from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_assemble_release():
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "assemble_release.py"),
                "--output-dir",
                tmp,
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        release_dir = Path(tmp) / "MediaHarbor"
        assert release_dir.is_dir()
        assert (release_dir / "AGENT_READ_ME_FIRST.md").is_file()
        assert (release_dir / "LICENSE").is_file()
        assert (release_dir / "skill" / "mediaharbor" / "SKILL.md").is_file()
        assert (release_dir / "skill" / "mediaharbor" / "scripts" / "_common.py").is_file()
        assert (release_dir / "download-tools" / "tools.json").is_file()
        assert (release_dir / "download-tools" / "routing.json").is_file()
        assert (release_dir / "download-tools" / ".mediaharbor-release").is_file()
        assert not (release_dir / "output").exists()
        assert not (release_dir / ".gitignore").exists()
        assert not (release_dir / "pyproject.toml").exists()
        assert not (release_dir / "tests").exists()


def test_release_scripts_run_independently():
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "assemble_release.py"),
                "--output-dir",
                tmp,
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        release_dir = Path(tmp) / "MediaHarbor"
        r = subprocess.run(
            [
                sys.executable,
                str(release_dir / "skill" / "mediaharbor" / "scripts" / "locate_root.py"),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=str(release_dir),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        r = subprocess.run(
            [
                sys.executable,
                str(release_dir / "skill" / "mediaharbor" / "scripts" / "check_tools.py"),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=str(release_dir),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        import json

        assert json.loads(r.stdout)["status"] == "DEGRADED"


def test_release_has_no_source_only_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "assemble_release.py"),
                "--output-dir",
                tmp,
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        release_dir = Path(tmp) / "MediaHarbor"
        items = {p.name for p in release_dir.iterdir()}
        assert "AGENT_READ_ME_FIRST.md" in items
        assert "skill" in items
        assert "download-tools" in items
        assert "AGENTS.md" not in items
        assert "tests" not in items


def test_force_refuses_non_release():
    with tempfile.TemporaryDirectory() as tmp:
        normal_dir = Path(tmp) / "MediaHarbor"
        normal_dir.mkdir()
        (normal_dir / "some_file.txt").write_text("hello")
        r = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "assemble_release.py"),
                "--output-dir",
                tmp,
                "--force",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert r.returncode != 0
        assert "No release marker" in r.stderr


def test_force_allows_marked_release():
    with tempfile.TemporaryDirectory() as tmp:
        release_dir = Path(tmp) / "MediaHarbor"
        release_dir.mkdir()
        (release_dir / "AGENT_READ_ME_FIRST.md").write_text("test")
        (release_dir / "skill" / "mediaharbor").mkdir(parents=True)
        (release_dir / "skill" / "mediaharbor" / "SKILL.md").write_text("---\nname: test\n---")
        (release_dir / "download-tools").mkdir(parents=True)
        (release_dir / "download-tools" / "tools.json").write_text("{}")
        marker_dir = release_dir / "download-tools"
        (marker_dir / ".mediaharbor-release").write_text(
            '{"marker":"mediaharbor-release","schema_version":1}'
        )
        r = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "assemble_release.py"),
                "--output-dir",
                tmp,
                "--force",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"


def test_shell_package_marker():
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "assemble_release.py"),
                "--output-dir",
                tmp,
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        marker = json.loads(
            (Path(tmp) / "MediaHarbor" / "download-tools" / ".mediaharbor-release").read_text(
                encoding="utf-8"
            )
        )
        assert marker["package_type"] == "shell"


def test_full_package_marker():
    with tempfile.TemporaryDirectory() as tmp:
        tool_src = Path(tmp) / "tools"
        tool_src.mkdir()
        (tool_src / "yt-dlp").mkdir(parents=True, exist_ok=True)
        (tool_src / "yt-dlp" / "yt-dlp.exe").write_bytes(b"fake yt-dlp")
        (tool_src / "ffmpeg").mkdir(parents=True, exist_ok=True)
        (tool_src / "ffmpeg" / "ffmpeg.exe").write_bytes(b"fake ffmpeg")
        (tool_src / "ffmpeg" / "ffprobe.exe").write_bytes(b"fake ffprobe")
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "assemble_release.py"),
                "--output-dir",
                tmp,
                "--tool-source",
                str(tool_src),
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        marker = json.loads(
            (Path(tmp) / "MediaHarbor" / "download-tools" / ".mediaharbor-release").read_text(
                encoding="utf-8"
            )
        )
        assert marker["package_type"] == "full"


def test_tool_manifest_includes_sha256_and_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        tool_src = Path(tmp) / "tools"
        tool_src.mkdir()
        (tool_src / "yt-dlp").mkdir(parents=True, exist_ok=True)
        (tool_src / "yt-dlp" / "yt-dlp.exe").write_bytes(b"fake yt-dlp binary content")
        (tool_src / "ffmpeg").mkdir(parents=True, exist_ok=True)
        (tool_src / "ffmpeg" / "ffmpeg.exe").write_bytes(b"fake ffmpeg bin")
        (tool_src / "ffmpeg" / "ffprobe.exe").write_bytes(b"fake ffprobe bin")
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "assemble_release.py"),
                "--output-dir",
                tmp,
                "--tool-source",
                str(tool_src),
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        manifest_path = Path(tmp) / "MediaHarbor" / "download-tools" / "tool-manifest.json"
        assert manifest_path.is_file()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "tools" in manifest
        ytdlp = manifest["tools"]["yt-dlp"]
        assert ytdlp["status"] == "copied"
        assert "sha256" in ytdlp
        assert len(ytdlp["sha256"]) == 64
        assert ytdlp["source"] == "https://github.com/yt-dlp/yt-dlp"
        assert "license" in ytdlp
        ffmpeg = manifest["tools"]["ffmpeg"]
        assert ffmpeg["status"] == "copied"
        assert "sha256" in ffmpeg
        assert "license" in ffmpeg
        assert ffmpeg["source"] == "https://ffmpeg.org"
