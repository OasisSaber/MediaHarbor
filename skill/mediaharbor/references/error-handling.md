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
| `BUDGET_EXHAUSTED` | Global attempt limit (`MAX_TOTAL_ATTEMPTS`) reached across all backends |

## Retry Policy

| Retryable | Non-Retryable (Terminal) |
|-----------|------------------------|
| TIMEOUT | DRM_DETECTED |
| DOWNLOAD_FAILED | AUTH_REQUIRED |
| OS_ERROR | GEO_RESTRICTED |
| RATE_LIMITED | UNSUPPORTED_URL |

### Backoff Strategy

Retryable failures follow exponential backoff with jitter between attempts:

- **Base delay**: 2 seconds
- **Max delay**: 60 seconds
- **Delay formula**: `min(2.0 * 2^(retry-1), 60.0) + random(0, delay * 0.5)`
- Delay is recorded in each `AttemptInfo.delay` field (0.0 for the first attempt)
- An injectable `sleep_fn` allows deterministic testing without real waits

### Global Attempt Budget

- `MAX_TOTAL_ATTEMPTS = 6` applies across all download backends for a single URL
- Before each backend, the remaining budget is computed; per-backend retries are capped to that budget (`min(route.max_retries, remaining)`)
- When the budget is exhausted, a `BUDGET_EXHAUSTED` result is returned (distinct from any per-backend failure)
- The final error status distinguishes "backend failed" from "global budget exhausted"

#### Probe vs. download boundary

The live probe (`probe_and_resolve_live`) runs once before the fallback loop and is **not** counted against `MAX_TOTAL_ATTEMPTS`. The budget only covers download attempts issued through `execute_backend`/`ProcessRunner.run` inside the fallback loop. Rationale: the probe is a single `yt-dlp --dump-json` call that decides routing (e.g. switching to a live route); charging it against the download budget would penalize streams that need a probe before any real download. The probe's own retries are bounded by the runner's `max_retries` and still produce their own `AttemptInfo` records, but those records are not merged into the final fallback `attempts` list.

## Principles

- All operations have a finite timeout
- Exit codes and stderr are captured for error classification
- Missing optional tools degrade gracefully
- No automatic tool installation or upgrade
- Tokens and auth params are redacted from logs
