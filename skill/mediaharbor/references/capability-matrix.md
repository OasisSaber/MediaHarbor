# MediaHarbor Capability Matrix

## Status Legend

| Code | Meaning |
|------|--------|
| VERIFIED | Implemented and verified by automated tests |
| FIXTURE_VERIFIED | Verified with local test fixtures only (no external tool needed) |
| PARTIAL | Partially implemented |
| EXTERNAL_NOT_VERIFIED | Requires external tools not available in test environment |
| NOT_IMPLEMENTED | Not yet implemented |

## Current Capabilities

| Area | Status |
|------|--------|
| Workspace layout | VERIFIED |
| Tool indexing (tools.json with schema validation) | VERIFIED |
| Root location (3-marker, cwd-independent) | VERIFIED |
| Tool existence check | VERIFIED |
| Current-platform tool path resolution | PARTIAL |
| ProcessRunner (controlled subprocess, no shell=True, retry) | VERIFIED |
| Error classification (13 operation statuses) | VERIFIED |
| yt-dlp adapter (probe + download with structured output) | FIXTURE_VERIFIED |
| ffprobe validation (media file verification) | FIXTURE_VERIFIED |
| Post-download validation chain | FIXTURE_VERIFIED |
| Static routing table (auditable JSON with validation) | VERIFIED |
| Multi-backend failover (3 backend limit, attempt history) | FIXTURE_VERIFIED |
| yutto adapter (Bilibili backend) | EXTERNAL_NOT_VERIFIED |
| Streamlink adapter (live stream backend) | EXTERNAL_NOT_VERIFIED |
| N_m3u8DL-RE adapter (HLS/DASH/MSS backend) | EXTERNAL_NOT_VERIFIED |
| gallery-dl adapter (social/gallery backend) | EXTERNAL_NOT_VERIFIED |
| URL sanitization | VERIFIED |
| Path validation (safe project names, anti-traversal) | VERIFIED |
| Acquisition projects (schema_version, project_id, atomic writes) | VERIFIED |
| Task state machine (PENDING/RUNNING/COMPLETED/FAILED/SKIPPED) | VERIFIED |
| Interrupted task and source transaction recovery | FIXTURE_VERIFIED |
| Orchestrator (candidate → router → download → ffprobe → hash → source.json → report) | FIXTURE_VERIFIED |
| source.json generation | FIXTURE_VERIFIED |
| Output organization (output/<project-name>/ subdirectories) | VERIFIED |
| Coverage reports | VERIFIED |
| Editor handoff with copyright notices | VERIFIED |
| Release assembly infrastructure (strict 3-item + marker protection) | VERIFIED |
| Release isolation (scripts run without source repo) | VERIFIED |
| Third-party binary provenance for full package | NOT_IMPLEMENTED |
| Stable complete-workflow CLI | NOT_IMPLEMENTED |
| CI (GitHub Actions, Ubuntu + Windows) | VERIFIED |
| Windows validation (validate.ps1) | VERIFIED |

## Known Limitations

- MediaHarbor uses a local, single-user experimental trust model; it is not a public arbitrary-URL download service
- The default search Harness uses public Bilibili and YouTube pages, while the download core may support other explicitly configured routes
- Per-URL human approval is not required; human review remains responsible for relevance, quality, copyright suitability, and final editing
- Shell/source distributions require external download tools to be configured separately
- Full-package third-party binary provenance, version, hash, and license verification is not complete; see Issue #27
- No auto-install or upgrade of download tools
- Current-platform tool resolution is incomplete and remains Windows-oriented in parts of the codebase
- System PATH fallback requires explicit opt-in
- No DRM bypass
- No video content understanding
- No automatic editing or timeline
- No built-in search engine in MediaHarbor core; search is supplied by the Agent / Harness
- No stable end-to-end public CLI yet
- No Web UI or database
- External live/test network requirement for real downloads
