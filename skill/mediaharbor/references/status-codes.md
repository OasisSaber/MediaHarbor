# Status Codes, Retry and Recovery

## Tool Statuses (check_tools)

| Status | Meaning |
|---|---|
| `READY` | All required tools available |
| `DEGRADED` | One or more required tools missing (degraded operation may continue) |
| `MISSING` | Tool not found at expected path |

Tool registry `tools.json`: schema_version=1; each tool declares roles, required, and platforms (per-platform relative paths). Paths must be relative; absolute paths, path traversal, and illegal characters are rejected. Platform resolution is Windows x64 primary; Linux/macOS are best-effort.

## Operation Status Codes

| Status | Meaning | Retryable |
|---|---|---|
| `SUCCESS` | Operation completed successfully | — |
| `TOOL_MISSING` | Required tool not found | no |
| `UNSUPPORTED_URL` | URL matches no route | no (terminal) |
| `AUTH_REQUIRED` | Login/authentication required | no (terminal) |
| `GEO_RESTRICTED` | Content not available in region | no (terminal) |
| `DRM_DETECTED` | DRM-protected content detected | no (terminal) |
| `RATE_LIMITED` | Rate limit reached | yes |
| `TIMEOUT` | Operation timed out | yes |
| `DOWNLOAD_FAILED` | General download failure | yes |
| `VALIDATION_FAILED` | Post-download validation failed | no |
| `OS_ERROR` | Operating system error | yes |
| `INTERNAL_ERROR` | Internal program error | no |
| `CONFIG_ERROR` | Configuration (routing.json/tools.json) invalid | no |

## Error Classification Rules

Classify from the return code and merged stdout+stderr, in priority order:

1. Return code 0 → `SUCCESS`.
2. `widevine`/`playready`/`fairplay`, or both `encrypted` and `drm` → `DRM_DETECTED`.
3. HTTP 401, `sign in`, `login required`, `private video` → `AUTH_REQUIRED`.
4. `geo-restricted`, `not available in your country` → `GEO_RESTRICTED`.
5. `too many requests`, `rate limit`, HTTP 429 → `RATE_LIMITED`.
6. `unsupported url`, `no video formats found` → `UNSUPPORTED_URL`.
7. Other non-zero return codes → `DOWNLOAD_FAILED`.
8. Timeout → `TIMEOUT`; process missing → `TOOL_MISSING`; other OSError → `OS_ERROR`.

## Retry Governance

- Retryable statuses retry within a backend up to the route's max_retries (1-5, default 2), then the next backend is tried.
- Total attempts per task are capped (6); exceeding the cap returns `RATE_LIMITED`.
- Terminal statuses are never retried.
- All external calls have finite timeouts (probe 30s, download 600s); captured stderr is capped (2000 bytes).

## Crash Recovery

- `project.json` is replaced atomically; `.bak` keeps the last valid committed version. A missing or corrupted main file is restored from `.bak` when loaded.
- The task state machine rejects invalid transitions (e.g., `COMPLETED → PENDING`); a rejected transition is treated as a programming error.
- Each started task has its own exception boundary; one failure does not block the queue.
- `RUNNING` tasks left by an interrupted process become `FAILED` on the next orchestration run ("Interrupted before task completion").
- Source manifests are staged as `<task_id>.source.pending` transactions and committed only after the task completes (`COMPLETED`); on recovery, pending transactions of completed tasks are published, and uncommitted transactions with their artifacts are removed.
- URL sanitization applies everywhere: sensitive query parameters (token, key, api_key, api-key, signature, sig, sign, auth, authorization, session, sessionid, expires, expiry, x-amz-signature, x-amz-credential, x-goog-signature, or any parameter name containing token/key/secret/sign/auth/session) are replaced with `REDACTED`; stdout/stderr get regex-based fallback sanitization.
- A sanitized URL containing `REDACTED` must not be used for real downloads; such tasks fail with an explanation.

## Principles

- All external operations have finite timeouts (probe ~30s, download ~600s) and finite retries.
- Missing optional tools degrade gracefully; download tools are never installed or upgraded automatically.
- System PATH fallback requires explicit opt-in; by default only registry-declared relative paths are used.
