from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_resolve_ffprobe_via_subprocess():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, r'"
            + str(REPO_ROOT / "skill" / "mediaharbor" / "scripts")
            + "'); from ffprobe_validator import resolve_ffprobe; r = resolve_ffprobe(); print(r)",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_validate_nonexistent_file():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, r'"
            + str(REPO_ROOT / "skill" / "mediaharbor" / "scripts")
            + "'); from pathlib import Path; from ffprobe_validator import validate_media; "
            "r = validate_media(Path('/nonexistent/file.mp4')); print(r.status)",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_get_media_info():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, r'"
            + str(REPO_ROOT / "skill" / "mediaharbor" / "scripts")
            + "'); from ffprobe_validator import get_media_info; "
            "data = {'format': {'duration': '30.5', 'size': '1000'}, "
            "'streams': [{'codec_type': 'video', 'width': 1920, 'height': 1080}, "
            "{'codec_type': 'audio'}]}; "
            "info = get_media_info(data); print(info['has_video'], info['duration'])",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "True 30.5" in result.stdout
