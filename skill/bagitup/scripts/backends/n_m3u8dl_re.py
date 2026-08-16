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


def resolve_n_m3u8dl_re(allow_system_path: bool = False) -> Path | None:
    try:
        result = resolve_registered_tool("n-m3u8dl-re", allow_system_path=allow_system_path)
        if result:
            return result
    except Exception:
        pass
    if allow_system_path:
        system = shutil.which("N_m3u8DL-RE")
        if system:
            return Path(system)
    return None


def run_n_m3u8dl_re(
    url: str,
    output_dir: Path,
    runner: ProcessRunner | None = None,
    max_attempts: int | None = None,
) -> BackendResult:
    if runner is None:
        runner = ProcessRunner()
    tool = resolve_n_m3u8dl_re()
    if tool is None:
        return BackendResult(
            status="TOOL_MISSING",
            stderr="N_m3u8DL-RE not found",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    before = snapshot_output_files(output_dir)
    cmd = [str(tool), url, "--save-dir", str(output_dir)]
    result = runner.run(cmd, backend="n-m3u8dl-re", check_drm=True, max_attempts=max_attempts)
    output_paths = discover_output_files(output_dir, before) if result.status == SUCCESS else []
    return BackendResult.from_process(result, output_paths)
