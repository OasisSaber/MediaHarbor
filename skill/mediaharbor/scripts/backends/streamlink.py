from __future__ import annotations

import shutil
from pathlib import Path

from _common import resolve_registered_tool
from process_runner import ProcessResult, ProcessRunner


def resolve_streamlink(allow_system_path: bool = False) -> Path | None:
    try:
        result = resolve_registered_tool("streamlink", allow_system_path=allow_system_path)
        if result:
            return result
    except Exception:
        pass
    if allow_system_path:
        system = shutil.which("streamlink")
        if system:
            return Path(system)
    return None


def run_streamlink(
    url: str, output_dir: Path, runner: ProcessRunner | None = None
) -> ProcessResult:
    if runner is None:
        runner = ProcessRunner()
    tool = resolve_streamlink()
    if tool is None:
        return ProcessResult(
            returncode=-1, stdout="", stderr="streamlink not found", status="TOOL_MISSING"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(tool), url, "best", "-o", str(output_dir / "stream.ts")]
    return runner.run(cmd, backend="streamlink", check_drm=True)
