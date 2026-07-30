from __future__ import annotations

import shutil
from pathlib import Path

from _common import resolve_registered_tool
from process_runner import (
    SUCCESS,
    BackendResult,
    ProcessRunner,
    discover_output_files,
    snapshot_output_files,
)


def resolve_yutto(allow_system_path: bool = False) -> Path | None:
    try:
        result = resolve_registered_tool("yutto", allow_system_path=allow_system_path)
        if result:
            return result
    except Exception:
        pass
    if allow_system_path:
        system = shutil.which("yutto")
        if system:
            return Path(system)
    return None


def run_yutto(url: str, output_dir: Path, runner: ProcessRunner | None = None) -> BackendResult:
    if runner is None:
        runner = ProcessRunner()
    tool = resolve_yutto()
    if tool is None:
        return BackendResult(
            status="TOOL_MISSING",
            stderr="yutto not found",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    before = snapshot_output_files(output_dir)
    cmd = [str(tool), url, "-d", str(output_dir)]
    result = runner.run(cmd, backend="yutto", check_drm=True)
    output_paths = discover_output_files(output_dir, before) if result.status == SUCCESS else []
    return BackendResult.from_process(result, output_paths)
