from __future__ import annotations

from pathlib import Path

from _common import resolve_registered_command
from process_runner import (
    SUCCESS,
    BackendResult,
    ProcessRunner,
    discover_output_files,
    snapshot_output_files,
)


def resolve_yutto() -> list[str] | None:
    return resolve_registered_command("yutto")


def _prefix(command: object) -> list[str]:
    if isinstance(command, (list, tuple)):
        return [str(item) for item in command]
    return [str(command)]


def run_yutto(
    url: str,
    output_dir: Path,
    runner: ProcessRunner | None = None,
    max_attempts: int | None = None,
) -> BackendResult:
    runner = runner or ProcessRunner()
    tool = resolve_yutto()
    if tool is None:
        return BackendResult(status="TOOL_MISSING", stderr="yutto not found")
    output_dir.mkdir(parents=True, exist_ok=True)
    before = snapshot_output_files(output_dir)
    cmd = [*_prefix(tool), url, "-d", str(output_dir)]
    result = runner.run(cmd, backend="yutto", check_drm=True, max_attempts=max_attempts)
    output_paths = discover_output_files(output_dir, before) if result.status == SUCCESS else []
    return BackendResult.from_process(result, output_paths)
