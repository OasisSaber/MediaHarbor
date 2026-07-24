from __future__ import annotations

import shutil
from pathlib import Path

from _common import resolve_registered_tool
from process_runner import ProcessResult, ProcessRunner


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
    url: str, output_dir: Path, runner: ProcessRunner | None = None
) -> ProcessResult:
    if runner is None:
        runner = ProcessRunner()
    tool = resolve_n_m3u8dl_re()
    if tool is None:
        return ProcessResult(
            returncode=-1, stdout="", stderr="N_m3u8DL-RE not found", status="TOOL_MISSING"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(tool), url, "--save-dir", str(output_dir)]
    return runner.run(cmd, backend="n-m3u8dl-re", check_drm=True)
