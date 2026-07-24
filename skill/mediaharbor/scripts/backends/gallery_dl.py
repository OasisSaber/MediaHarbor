from __future__ import annotations

from pathlib import Path

from _common import resolve_registered_tool
from process_runner import ProcessResult, ProcessRunner


def resolve_gallery_dl(allow_system_path: bool = False) -> Path | None:
    return resolve_registered_tool("gallery-dl", allow_system_path=allow_system_path)


def run_gallery_dl(
    url: str, output_dir: Path, runner: ProcessRunner | None = None
) -> ProcessResult:
    if runner is None:
        runner = ProcessRunner()
    tool = resolve_gallery_dl()
    if tool is None:
        return ProcessResult(
            returncode=-1, stdout="", stderr="gallery-dl not found", status="TOOL_MISSING"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(tool), url, "-d", str(output_dir)]
    return runner.run(cmd, backend="gallery-dl", check_drm=True)
