# Error Handling

## Tool Check Statuses

| Status | Meaning |
|---|---|
| `READY` | All required tools available |
| `DEGRADED` | One or more required tools missing |
| `MISSING` | Tool not found at expected path |

## Operation Statuses

| Status | Meaning |
|---|---|
| `SUCCESS` | Operation completed successfully |
| `TOOL_MISSING` | Required tool not found |
| `UNSUPPORTED_URL` | URL protocol not supported |
| `AUTH_REQUIRED` | Login or authentication required |
| `GEO_RESTRICTED` | Content not available in region |
| `DRM_DETECTED` | Protected/DEM content |
| `RATE_LIMITED` | Rate limit reached |
| `TIMEOUT` | Operation timed out |
| `DOWNLOAD_FAILED` | General download failure |
| `VALIDATION_FAILED` | Post-download validation failed |
| `OS_ERROR` | Operating system error |
| `INTERNAL_ERROR` | Internal program error |
| `CONFIG_ERROR` | Configuration file (routing.json, tools.json) is invalid |

## Retry Policy

| Retryable | Non-Retryable (Terminal) |
|-----------|------------------------|
| TIMEOUT | DRM_DETECTED |
| DOWNLOAD_FAILED | AUTH_REQUIRED |
| OS_ERROR | GEO_RESTRICTED |
| RATE_LIMITED | UNSUPPORTED_URL |

## Principles

- All operations have a finite timeout
- Exit codes and stderr are captured for error classification
- Missing optional tools degrade gracefully
- No automatic tool installation or upgrade
- Tokens and auth params are redacted from logs

## Crash Recovery

- `project.json` is replaced atomically; `.bak` keeps the last valid committed version.
- A missing or invalid `project.json` is restored from a valid `.bak` when loaded.
- Each started task has its own exception boundary, so one failure does not stop the queue.
- Tasks left `RUNNING` by an interrupted process become `FAILED` on the next orchestration run.
- A source manifest is staged as a local pending transaction before project completion. Completed
  transactions are published on recovery; uncommitted transactions and their artifacts are removed.
