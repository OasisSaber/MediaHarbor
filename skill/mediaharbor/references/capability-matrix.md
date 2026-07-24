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
| ProcessRunner (controlled subprocess, no shell=True, retry) | VERIFIED |
| Error classification (12 operation statuses) | VERIFIED |
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
| Orchestrator (candidate → router → download → ffprobe → hash → source.json → report) | FIXTURE_VERIFIED |
| source.json generation | FIXTURE_VERIFIED |
| Output organization (output/<project-name>/ subdirectories) | VERIFIED |
| Coverage reports | VERIFIED |
| Editor handoff with copyright notices | VERIFIED |
| Release assembly (strict 3-item + marker protection) | VERIFIED |
| Release isolation (scripts run without source repo) | VERIFIED |
| CI (GitHub Actions, Ubuntu + Windows) | VERIFIED |
| Windows validation (validate.ps1) | VERIFIED |

## Known Limitations

- External download tools required (not bundled)
- No auto-install or upgrade of download tools
- System PATH fallback requires explicit opt-in
- No DRM bypass
- No video content understanding
- No automatic editing or timeline
- No built-in search engine
- No Web UI or database
- External live/test network requirement for real downloads
