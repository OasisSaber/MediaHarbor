from __future__ import annotations

import shutil
from pathlib import Path

from _common import resolve_registered_tool
from process_runner import SUCCESS, BackendResult, ProcessRunner, discover_output_files


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
    cmd = [str(tool), url, "--save-dir", str(output_dir)]
    result = runner.run(cmd, backend="n-m3u8dl-re", check_drm=True)
    output_paths = discover_output_files(output_dir) if result.status == SUCCESS else []
    return BackendResult(
        status=result.status,
        output_paths=output_paths,
        stdout=result.stdout,
        stderr=result.stderr,
        attempts=result.attempts,
    )
