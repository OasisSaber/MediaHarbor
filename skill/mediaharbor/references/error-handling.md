# Error Handling

## Structured Status Values

| Status | Meaning |
|---|---|
| `READY` | Tool available |
| `UNSUPPORTED` | URL protocol not supported |
| `AUTH_REQUIRED` | Login required |
| `GEO_RESTRICTED` | Region blocked |
| `DRM_DETECTED` | Protected content |
| `RATE_LIMITED` | Rate limited |
| `DOWNLOAD_FAILED` | General failure |

## Principles

- All operations have a finite timeout.
- Exit codes and stderr are captured for error classification.
- Missing optional tools degrade gracefully.
- No automatic tool installation or upgrade.
