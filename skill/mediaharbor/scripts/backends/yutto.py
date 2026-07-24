from __future__ import annotations

from pathlib import Path

from _common import resolve_registered_tool
from process_runner import ProcessResult, ProcessRunner


def resolve_yutto(allow_system_path: bool = False) -> Path | None:
    return resolve_registered_tool("yutto", allow_system_path=allow_system_path)


def run_yutto(url: str, output_dir: Path, runner: ProcessRunner | None = None) -> ProcessResult:
    if runner is None:
        runner = ProcessRunner()
    tool = resolve_yutto()
    if tool is None:
        return ProcessResult(
            returncode=-1, stdout="", stderr="yutto not found", status="TOOL_MISSING"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(tool), url, "-d", str(output_dir)]
    return runner.run(cmd, backend="yutto", check_drm=True)
