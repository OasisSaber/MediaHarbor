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
