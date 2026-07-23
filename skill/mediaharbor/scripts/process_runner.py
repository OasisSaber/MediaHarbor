from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Sequence
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

PROBE_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 600
MAX_RETRIES = 3
MAX_TOTAL_ATTEMPTS = 6

TOOL_STATUSES = {"READY", "DEGRADED", "MISSING"}
SUCCESS = "SUCCESS"
OP_STATUSES = {
    SUCCESS,
    "TOOL_MISSING",
    "UNSUPPORTED_URL",
    "AUTH_REQUIRED",
    "GEO_RESTRICTED",
    "DRM_DETECTED",
    "RATE_LIMITED",
    "TIMEOUT",
    "DOWNLOAD_FAILED",
    "VALIDATION_FAILED",
    "OS_ERROR",
    "INTERNAL_ERROR",
    "CONFIG_ERROR",
}

RETRYABLE_STATUSES = {
    "TIMEOUT",
    "DOWNLOAD_FAILED",
    "OS_ERROR",
    "RATE_LIMITED",
}

TERMINAL_STATUSES = {
    "DRM_DETECTED",
    "AUTH_REQUIRED",
    "GEO_RESTRICTED",
    "UNSUPPORTED_URL",
}

SENSITIVE_PARAMS = {
    "token",
    "key",
    "api_key",
    "api-key",
    "signature",
    "sig",
    "sign",
    "auth",
    "authorization",
    "session",
    "sessionid",
    "expires",
    "expiry",
    "x-amz-signature",
    "x-amz-credential",
    "x-goog-signature",
}
URL_REDACTION_RE = re.compile(
    r"(token|key|secret|auth|session|pass|sign|sig)=[^&\s]*", re.IGNORECASE
)


@dataclass
class AttemptInfo:
    attempt_number: int
    backend: str | None
    status: str
    returncode: int
    elapsed: float
    retryable: bool
    safe_error: str


@dataclass
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed: float = 0.0
    status: str = "INTERNAL_ERROR"
    attempts: list[AttemptInfo] = field(default_factory=list)


def sanitize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {}
        for key, values in params.items():
            key_lower = key.lower()
            if key_lower in SENSITIVE_PARAMS or any(
                s in key_lower for s in ("token", "key", "secret", "sign", "auth", "session")
            ):
                cleaned[key] = ["REDACTED"]
            else:
                cleaned[key] = values
        new_query = urlencode(cleaned, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return URL_REDACTION_RE.sub(lambda m: m.group().split("=")[0] + "=REDACTED", url)


def sanitize_stderr(stderr: str) -> str:
    return URL_REDACTION_RE.sub("***=REDACTED", stderr)


def sanitize_stdout(stdout: str) -> str:
    return URL_REDACTION_RE.sub("***=REDACTED", stdout)


class ProcessRunner:
    def __init__(self, timeout: int = PROBE_TIMEOUT, max_retries: int = MAX_RETRIES):
        self.timeout = timeout
        self.max_retries = max_retries

    def run(
        self,
        cmd: Sequence[str],
        check_drm: bool = True,
        backend: str | None = None,
        allow_system_path: bool = False,
    ) -> ProcessResult:
        attempts: list[AttemptInfo] = []
        last_result = ProcessResult(returncode=-1, stdout="", stderr="", status="INTERNAL_ERROR")

        for attempt_num in range(1, self.max_retries + 1):
            result = self._run_once(cmd, check_drm)
            result.stdout = sanitize_stdout(result.stdout)
            result.stderr = sanitize_stderr(result.stderr)

            info = AttemptInfo(
                attempt_number=attempt_num,
                backend=backend,
                status=result.status,
                returncode=result.returncode,
                elapsed=result.elapsed,
                retryable=result.status in RETRYABLE_STATUSES,
                safe_error=result.stderr[:200],
            )
            attempts.append(info)
            last_result = result
            last_result.attempts = attempts

            if result.status == SUCCESS:
                return last_result

            if result.status in TERMINAL_STATUSES:
                return last_result

            if result.status not in RETRYABLE_STATUSES:
                return last_result

        return last_result

    def _run_once(self, cmd: Sequence[str], check_drm: bool) -> ProcessResult:
        if not cmd or not all(isinstance(a, str) and a for a in cmd):
            return ProcessResult(
                returncode=-1,
                stdout="",
                stderr="Invalid command arguments",
                status="INTERNAL_ERROR",
            )

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            elapsed = time.monotonic() - start
            stderr_lower = proc.stderr.lower()
            stdout_lower = proc.stdout.lower()
            combined = stderr_lower + stdout_lower
            status = self._classify(proc.returncode, combined, check_drm)
            return ProcessResult(
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                elapsed=elapsed,
                status=status,
            )
        except subprocess.TimeoutExpired:
            return ProcessResult(
                returncode=-1,
                stdout="",
                stderr=f"Timeout after {self.timeout}s",
                elapsed=time.monotonic() - start,
                status="TIMEOUT",
            )
        except FileNotFoundError:
            return ProcessResult(
                returncode=-1,
                stdout="",
                stderr=f"Command not found: {cmd[0] if cmd else '?'}",
                elapsed=time.monotonic() - start,
                status="TOOL_MISSING",
            )
        except OSError as e:
            return ProcessResult(
                returncode=-1,
                stdout="",
                stderr=str(e),
                elapsed=time.monotonic() - start,
                status="OS_ERROR",
            )

    def _classify(self, returncode: int, combined: str, check_drm: bool) -> str:
        if returncode == 0:
            return SUCCESS

        drm_keywords = ["widevine", "playready", "fairplay"]
        if check_drm and any(k in combined for k in drm_keywords):
            return "DRM_DETECTED"
        if check_drm and "encrypted" in combined and "drm" in combined:
            return "DRM_DETECTED"

        if "http error 401" in combined or "sign in" in combined or "login required" in combined:
            return "AUTH_REQUIRED"
        if "private video" in combined:
            return "AUTH_REQUIRED"

        if "geo-restricted" in combined:
            return "GEO_RESTRICTED"
        if "not available in your country" in combined or "blocked in your country" in combined:
            return "GEO_RESTRICTED"

        if any(p in combined for p in ["too many requests", "rate limit"]):
            return "RATE_LIMITED"
        if "429" in combined and "http" in combined:
            return "RATE_LIMITED"

        if "unsupported url" in combined or "no video formats found" in combined:
            return "UNSUPPORTED_URL"

        return "DOWNLOAD_FAILED"
