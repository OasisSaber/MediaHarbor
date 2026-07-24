from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "skill" / "mediaharbor" / "scripts")
)
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


def test_attempt_limit_caps_retries():
    runner = ProcessRunner(max_retries=10)
    result = runner.run(
        [sys.executable, "-c", "exit(1)"],
        attempt_limit=2,
    )
    assert len(result.attempts) == 2
    assert result.status == "DOWNLOAD_FAILED"


def test_attempt_limit_one_does_single_attempt():
    runner = ProcessRunner(max_retries=5)
    result = runner.run([sys.executable, "-c", "exit(1)"], attempt_limit=1)
    assert len(result.attempts) == 1


def test_attempt_limit_greater_than_max_retries():
    runner = ProcessRunner(max_retries=2)
    result = runner.run([sys.executable, "-c", "exit(1)"], attempt_limit=10)
    assert len(result.attempts) == 2


def test_backoff_delay_recorded():
    delays = []

    def recording_sleep(secs):
        delays.append(secs)

    runner = ProcessRunner(max_retries=3, sleep_fn=recording_sleep)
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('too many requests'); exit(1)"]
    )
    assert len(result.attempts) == 3
    assert result.attempts[0].delay == 0.0
    assert result.attempts[1].delay > 0
    assert result.attempts[2].delay > 0
    assert len(delays) == 2


def test_backoff_increases_with_retries():
    delays = []

    def recording_sleep(secs):
        delays.append(secs)

    runner = ProcessRunner(max_retries=4, sleep_fn=recording_sleep)
    result = runner.run([sys.executable, "-c", "exit(1)"])
    assert len(result.attempts) == 4
    assert len(delays) == 3
    assert delays[0] < delays[1] < delays[2]


def test_injectable_sleep_called():
    sleep_log = []

    def fake_sleep(secs):
        sleep_log.append(secs)

    runner = ProcessRunner(max_retries=2, sleep_fn=fake_sleep)
    runner.run([sys.executable, "-c", "exit(1)"])
    assert len(sleep_log) == 1


def test_no_sleep_on_success():
    sleep_log = []

    def fake_sleep(secs):
        sleep_log.append(secs)

    runner = ProcessRunner(max_retries=3, sleep_fn=fake_sleep)
    runner.run([sys.executable, "-c", "print('ok')"])
    assert len(sleep_log) == 0


def test_terminal_status_no_retry_with_attempt_limit():
    runner = ProcessRunner(max_retries=5)
    result = runner.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('unsupported url'); exit(1)"],
        attempt_limit=3,
    )
    assert result.status == "UNSUPPORTED_URL"
    assert len(result.attempts) == 1
