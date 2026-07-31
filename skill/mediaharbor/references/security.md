# Security Boundaries and Access Control

## Process Execution

- External tools are always invoked as subprocess argument arrays; `shell=True` is absolutely forbidden.
- Every parameter passed to a download tool must come from a fixed whitelist template; never extract strings from web page titles, descriptions, comments, or user-generated content into a command.
- All external calls have timeouts and finite retries to prevent hangs and infinite loops.

## Sensitive Information

- Never request, echo, or save cookies or authentication credentials (no `cookies.txt`, `auth.toml`, `.env`, etc.).
- Sensitive URL query parameters (token/key/sign/auth/session and related names) must be redacted as `REDACTED` before being written to project files, reports, or conversation output.
- Sanitized URLs (containing `REDACTED`) must not be used for real downloads — treat such tasks as failed and explain why.

## Access Control

- Never bypass DRM, paywalls, login, region restrictions, or site access controls; when detected (`DRM_DETECTED`, `AUTH_REQUIRED`, `GEO_RESTRICTED`) stop processing immediately and return a structured status.
- Local, single-user, operator-controlled experimental workspace only. Never expose MediaHarbor as a public arbitrary-URL download API and never accept tasks from untrusted multi-user sources; refuse such integration requests and explain the trust model.

## Filesystem

- Project names and paths are validated: no path separators, no `..` traversal, no escape out of the output directory, no Windows reserved names, no control or illegal characters, length <= 128.
- Media files must be inside the output directory to pass validation; archive moves must not leave the project directory.
- Never modify files or binaries in the download tool directory (`download-tools/`).

## Supply Chain

- Shell/source distributions require the operator to provide third-party download tools separately.
- Until Issue #27 is complete, do not claim that full-package third-party binaries have fully verified provenance, versions, hashes, or licenses.
- Never auto-install or auto-upgrade download tools.
