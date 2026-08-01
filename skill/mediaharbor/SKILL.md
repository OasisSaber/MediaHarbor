---
name: mediaharbor
description: Collect video editing materials for an existing script with MediaHarbor: analyze the script for people, events, years, locations and visual needs, generate multi-strategy search terms, search candidate video pages (default Bilibili and YouTube), enqueue candidate URLs, download through local tools, ffprobe-validate, archive, and hand off to the human editor. Trigger when the user provides a script or copy and asks to find, download, or collect video materials, or explicitly activates MediaHarbor.
---

# MediaHarbor Skill

## Trigger

The human provides an existing script or text and asks to find matching video materials, OR the human explicitly activates MediaHarbor for material collection.

## Scope and Installation

- MediaHarbor is a **local, single-user, Windows x64 first** agent-skill source repository. Current official platform: **Windows x64 only**.
- Runtime requirements: Windows x64, **Python 3.11+**, and local third-party tools configured per `download-tools/tools.json`.
- Deployment: clone the whole repository into the agent workspace (no pip install, no build step).
- Obtain third-party download tools separately and place them under `download-tools/<tool>/` exactly as declared in `download-tools/tools.json` (e.g. `download-tools/yt-dlp/yt-dlp.exe`). MediaHarbor never downloads, installs, or upgrades tools.
- A unified agent-facing CLI is tracked in Issue #29 and is **not implemented yet**; until then the internal scripts under `skill/mediaharbor/scripts/` are the only entry points (see "Internal Entry Points").

## Roles

- **Agent (this model)**: understands the script, generates search terms, searches and filters candidate URLs, submits download tasks, organizes and reports.
- **MediaHarbor core**: discovers and checks tools, invokes download tools under controlled subprocesses, provides limited failover, media validation, archiving, and reporting.
- **Human editor**: judges material relevance, quality, and copyright suitability, and performs the final editing. Human review is not a mandatory security gate before each download.

## Default Workflow (end to end)

1. **Analyze the script**: extract people, events, years, locations, time spans, and visual needs.
2. **Generate search terms**: cover multiple strategies (keyword, reverse image description, scene description).
3. **Search candidate pages**: default scope is public Bilibili and YouTube pages; this is a default search scope, not a hard hostname allowlist in the download core.
4. **Enqueue candidate URLs**: add candidate URLs to the acquisition project task queue (status `PENDING`).
5. **Controlled download**: match the routing table, select a backend, invoke the local download tool via a subprocess argument array, fail over across a limited number of backends in order (default max 3).
6. **Validate**: ffprobe checks a non-empty file, location inside the output directory, parseable media, duration > 0, and a video stream.
7. **Archive**: rename to `task_id-original name`, move to `assets/originals/`, write per-source `source.json` manifests (sha256 + ffprobe metadata), update the project materials table.
8. **Report and hand off**: generate a coverage report and a human editor handoff document; the human reviews and edits.

## Trust Model

- Designed for a local, single-user experimental workspace controlled by the operator.
- The Agent may submit and download supported candidates unattended; per-URL human approval is not required.
- Bilibili and YouTube are the default search scope, not a hard hostname allowlist in the download core; other URLs are processed only when explicitly supported by `routing.json`, configured backends, and local tools.
- Do not expose MediaHarbor as a public arbitrary-URL download API or accept tasks from untrusted multi-user sources.

## Directory Layout

```
MediaHarbor/  (repository root = workspace root)
├─ AGENT_READ_ME_FIRST.md     # Agent entry point (read first)
├─ skill/mediaharbor/         # The skill
│  ├─ SKILL.md                # Unique authoritative skill document (this file)
│  └─ scripts/                # Runnable Python modules (no pip install needed)
├─ download-tools/            # Tool index (tools.json, routing.json) + tool binaries
└─ output/                    # Created on first use
   └─ <project-name>/
      ├─ project.json         # Project state (atomic writes, .bak fallback)
      ├─ input/               # Original script
      ├─ planning/            # Story nodes and search plans
      ├─ acquisition/         # Task/material state + sources/<source_id>.json
      ├─ assets/originals/    # Final archived media (task_id-original name)
      ├─ logs/
      └─ reports/             # COVERAGE_REPORT.md + HUMAN_EDITOR_HANDOFF.md
```

Project names must be safe: no path separators, no path traversal (`..`), no Windows reserved names (CON/PRN/AUX/NUL/COM1-9/LPT1-9), no illegal characters `<>:"|?*` or control characters, length <= 128.

## Tool Check

Before downloading, run:

```bash
python skill/mediaharbor/scripts/check_tools.py --json
```

Returns `READY`, `DEGRADED`, or missing tool status.

Required tools: yt-dlp (probe/VOD/subtitles/metadata), ffmpeg (merge/convert), ffprobe (validation).
Optional tools: yutto (Bilibili), streamlink (live), N_m3u8DL-RE (HLS/DASH/MSS), gallery-dl (social/galleries).

## Controlled Subprocess Rules

- Always invoke with argument arrays (no `shell=True`); parameters must be whitelisted; never build commands from arbitrary strings found in web page titles, descriptions, or comments.
- All operations have finite timeouts; retry counts are finite.
- Sensitive URL parameters (token/key/sign/auth/session etc.) are redacted as `REDACTED` and oversized parameter values are truncated in display URLs; tasks keep the raw execution URL for routing, probe, and download, while logs, reports, and agent output use the sanitized display URL.

## Status Codes

Tool statuses: `READY`, `DEGRADED`, `MISSING`.

Operation statuses (13): `SUCCESS`, `TOOL_MISSING`, `UNSUPPORTED_URL`, `AUTH_REQUIRED`, `GEO_RESTRICTED`, `DRM_DETECTED`, `RATE_LIMITED`, `TIMEOUT`, `DOWNLOAD_FAILED`, `VALIDATION_FAILED`, `OS_ERROR`, `INTERNAL_ERROR`, `CONFIG_ERROR`.

- Not retried within a backend (terminal): `DRM_DETECTED`, `AUTH_REQUIRED`, `GEO_RESTRICTED`, `UNSUPPORTED_URL`.
- Retryable: `TIMEOUT`, `DOWNLOAD_FAILED`, `OS_ERROR`, `RATE_LIMITED`.
- `DRM_DETECTED`, `AUTH_REQUIRED`, and `GEO_RESTRICTED` stop cross-backend failover immediately. `UNSUPPORTED_URL` is returned when no route matches; its cross-backend stop semantics are unified by Issue #16.

## Error Classification

Classify failures from the return code and merged stdout+stderr, in priority order:

1. Return code 0 → `SUCCESS`.
2. `widevine`/`playready`/`fairplay`, or both `encrypted` and `drm` → `DRM_DETECTED`.
3. HTTP 401, `sign in`, `login required`, `private video` → `AUTH_REQUIRED`.
4. `geo-restricted`, `not available in your country` → `GEO_RESTRICTED`.
5. `too many requests`, `rate limit`, HTTP 429 → `RATE_LIMITED`.
6. `unsupported url`, `no video formats found` → `UNSUPPORTED_URL`.
7. Other non-zero return codes → `DOWNLOAD_FAILED`.
8. Timeout → `TIMEOUT`; process missing → `TOOL_MISSING`; other OSError → `OS_ERROR`.

## Retry and Recovery

- Each backend uses a finite retry count (route `max_retries`, 1-5, default 2); a route selects at most a limited number of backends (default 3). Terminal statuses are never retried within a backend.
- The code contains a `MAX_TOTAL_ATTEMPTS` guard that can return `RATE_LIMITED`, but strict enforcement of a global cross-backend attempt budget is still tracked by Issue #16.
- No backoff between retries and no additional decoding protection are implemented yet.
- All external calls have finite timeouts (probe 30s, download 600s); captured stderr is capped at 2000 characters.
- `project.json` is replaced atomically; `.bak` keeps the last valid committed version and is used for restore on load.
- Each task is normally processed behind an exception boundary, so ordinary task failures do not stop the queue. The post-completion source-finalization exception window tracked by Issue #35 is not fully isolated yet. `RUNNING` tasks left by an interrupted process become `FAILED` on the next run ("Interrupted before task completion").
- Source manifests are staged as `<task_id>.source.pending` transactions and committed only after the task completes; on recovery, pending transactions of completed tasks are published and uncommitted ones with their artifacts are removed.

## Project Data Structures

- **Task state machine**: `PENDING → RUNNING → COMPLETED/FAILED`, `FAILED → PENDING` (retry), `PENDING → SKIPPED`, `SKIPPED → PENDING`. Invalid transitions are treated as programming errors.
- **Source manifest**: each successful source produces `source.json` with source_id, display_url (sanitized), selected_backend, attempt_history (backend/status/error per attempt), local_files, subtitles, thumbnail, sha256, ffprobe_result (format/duration/resolution/codecs), acquisition_timestamp, and a copyright notice.
- **Routing table** (`download-tools/routing.json`): schema_version=1; entries carry name, patterns (regex list), backends (ordered list limited to yt-dlp/yutto/streamlink/n-m3u8dl-re/gallery-dl), max_retries (1-5), drm_stop. Routes are matched in order; the first hit applies. Editing only allows whitelisted backend names and validated regex.

## Reports and Handoff

- `COVERAGE_REPORT.md`: total/completed/failed/pending task counts, candidate URLs and status per story node, material list.
- `HUMAN_EDITOR_HANDOFF.md`: material paths, sources, durations, resolutions; original script; important note — a successful download does not mean the material fits the edit; the human is responsible for clip selection, pacing, narrative fit, and verifying copyright before publication.

Reports refresh automatically after each queue processing round.

## Security Boundaries (hard constraints)

- Never request, echo, or save cookies or credentials (no `cookies.txt`, `auth.toml`, `.env`).
- Never bypass DRM, paywalls, login, region restrictions, or site access controls; stop and return a structured status.
- Never construct commands from web page content; never modify files or binaries in the download tool directory.
- Do not claim capabilities that are not implemented (no video content understanding, no automatic editing, no built-in search engine).

## Known Reliability Limits

The following reliability issues remain open; do not treat them as implemented:

- **Issue #14**: URLs with sensitive or signed query parameters currently lack a complete model that preserves both the executable URL and a safe display URL.
- **Issue #16**: strict global attempt budgeting, backoff, and additional decoding protection are not finished.
- **Issue #34**: on partial failure during multi-file moves, files already moved into the final directory have no full rollback guarantee.
- **Issue #35**: after a task is marked completed, the state protection boundary still needs work if source transaction finalization fails.
- **Issue #29**: the unified agent-facing CLI is not implemented.

## Internal Entry Points

Until Issue #29 (unified agent-facing CLI) is implemented, the following internal scripts are the only entry points. They are internal, not recommended as a public API:

| Script | Purpose |
|---|---|
| `locate_root.py` | Print the MediaHarbor root path (3-marker, cwd-independent) |
| `check_tools.py` | Print tool availability status (READY/DEGRADED) |
| `orchestrator.py` | Process the task queue (download → validate → hash → source.json → reports) |
| `router.py` | Route a URL to backends per routing.json with failover |
| `probe.py` | **Internal diagnostic entry**: probe URLs with yt-dlp |
| `download.py` | **Legacy / internal**: single-URL download helper; not part of the normal skill workflow, kept until #29 |
| `acquisition.py`, `project.py`, `report.py`, `process_runner.py`, `ffprobe_validator.py`, `ytdlp_adapter.py`, `safe_path.py`, `_common.py` | Library modules used by the above |

## Current Status

Experimental release phase. The core acquisition chain is implemented: portable workspace layout, tool indexing and checking, controlled process execution, yt-dlp probing and download, ffprobe validation, multi-backend routing and failover, acquisition project management, task queue, source metadata, and reports.

Current official platform is Windows x64. The Ubuntu CI job only proves that the pure-Python tests run; it is not a Linux platform support statement. Real downloads depend on locally installed third-party tools, site state, and routing configuration.
