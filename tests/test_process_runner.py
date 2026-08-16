from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "bagitup" / "scripts"))
from process_runner import ProcessRunner


def test_returns_success():
    runner = ProcessRunner()
    result = runner.run([sys.executable, "-c", "print('ok')"])
    assert result.status == "SUCCESS"
    assert result.returncode == 0
    assert "ok" in result.stdout


def test_captures_stderr():
    runner = ProcessRunner()
    result = runner.run([sys.executable, "-c", "import sys; sys.stderr.write('err')"])
    assert "err" in result.stderr


def test_non_zero_exit():
    runner = ProcessRunner()
    result = runner.run([sys.executable, "-c", "exit(1)"])
    assert result.returncode == 1
    assert result.status != "SUCCESS"


def test_timeout():
    runner = ProcessRunner(timeout=1, max_retries=1)
    result = runner.run([sys.executable, "-c", "import time; time.sleep(10)"])
    assert result.status == "TIMEOUT"


def test_missing_command():
    runner = ProcessRunner(max_retries=1)
    result = runner.run(["nonexistent-command-hopefully"])
    assert result.status == "TOOL_MISSING"


def test_classifies_auth_required():
    runner = ProcessRunner(max_retries=1)
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('HTTP Error 401'); exit(1)"]
    )
    assert result.status == "AUTH_REQUIRED"


def test_classifies_drm():
    runner = ProcessRunner(max_retries=1)
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('Widevine DRM'); exit(1)"],
    )
    assert result.status == "DRM_DETECTED"


def test_classifies_geo_restricted():
    runner = ProcessRunner(max_retries=1)
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('geo-restricted'); exit(1)"]
    )
    assert result.status == "GEO_RESTRICTED"


def test_classifies_rate_limited():
    runner = ProcessRunner(max_retries=1)
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('too many requests'); exit(1)"]
    )
    assert result.status == "RATE_LIMITED"


def test_classifies_unsupported():
    runner = ProcessRunner(max_retries=1)
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('unsupported url'); exit(1)"]
    )
    assert result.status == "UNSUPPORTED_URL"


def test_retry_on_failure():
    runner = ProcessRunner(timeout=30, max_retries=3)
    result = runner.run([sys.executable, "-c", "import time; time.sleep(0.1); exit(1)"])
    assert result.status == "DOWNLOAD_FAILED"
    assert len(result.attempts) == 3


def test_no_retry_on_auth():
    runner = ProcessRunner(max_retries=3)
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('HTTP Error 401'); exit(1)"]
    )
    assert result.status == "AUTH_REQUIRED"
    assert len(result.attempts) == 1


def test_attempts_recorded():
    runner = ProcessRunner(max_retries=2)
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('too many requests'); exit(1)"]
    )
    assert len(result.attempts) >= 1
    for a in result.attempts:
        assert a.attempt_number >= 1
        assert a.status in ("RATE_LIMITED",)


def test_discover_output_files_in_nested_backend_directory(tmp_path):
    from process_runner import discover_output_files, snapshot_output_files

    before = snapshot_output_files(tmp_path)
    nested = tmp_path / "site" / "author" / "video.mp4"
    nested.parent.mkdir(parents=True)
    nested.write_text("media")

    assert discover_output_files(tmp_path, before) == [nested]


def test_max_attempts_caps_executions():
    runner = ProcessRunner(max_retries=5)
    result = runner.run(
        [sys.executable, "-c", "exit(1)"],
        max_attempts=2,
    )
    assert len(result.attempts) == 2
    assert all(a.status == "DOWNLOAD_FAILED" for a in result.attempts)


def test_max_attempts_one_allows_single_execution():
    runner = ProcessRunner(max_retries=5)
    result = runner.run(
        [sys.executable, "-c", "exit(1)"],
        max_attempts=1,
    )
    assert len(result.attempts) == 1


def test_retryable_failures_apply_injected_backoff():
    delays = []

    def recording_backoff(delay: float) -> None:
        delays.append(delay)

    runner = ProcessRunner(max_retries=3, backoff=recording_backoff)
    result = runner.run([sys.executable, "-c", "exit(1)"])
    assert result.returncode == 1
    assert len(result.attempts) == 3
    assert len(delays) == 2
    assert delays[0] <= delays[1]
    assert all(d > 0 for d in delays)


def test_terminal_status_no_backoff():
    delays = []

    def recording_backoff(delay: float) -> None:
        delays.append(delay)

    runner = ProcessRunner(max_retries=3, backoff=recording_backoff)
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('Widevine DRM'); exit(1)"]
    )
    assert result.status == "DRM_DETECTED"
    assert len(result.attempts) == 1
    assert delays == []


def test_invalid_utf8_output_does_not_crash():
    runner = ProcessRunner()
    script = (
        "import sys; sys.stdout.buffer.write(b'\\xff\\xfe broken bytes'); "
        "sys.stdout.buffer.flush(); exit(0)"
    )
    result = runner.run([sys.executable, "-c", script])
    assert result.status == "SUCCESS"
    assert "\\ufffd" in result.stdout or "broken" in result.stdout
