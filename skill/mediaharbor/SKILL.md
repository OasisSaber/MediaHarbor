---
name: mediaharbor
description: Collect video editing materials for an existing script with MediaHarbor: analyze the script for people, events, years, locations and visual needs, generate multi-strategy search terms, search candidate video pages (default Bilibili and YouTube), enqueue candidate URLs, download through local tools, ffprobe-validate, archive, and hand off to the human editor. Trigger when the user provides a script or copy and asks to find, download, or collect video materials, or explicitly activates MediaHarbor.
---

## Trigger

The human provides an existing script or text and asks to find matching video materials, OR the human explicitly activates MediaHarbor for material collection.

## Roles

- **Agent (this model)**: understands the script, generates search terms, searches and filters candidate URLs, submits download tasks, organizes and reports.
- **MediaHarbor core**: discovers and checks tools, invokes download tools under controlled subprocesses, provides limited failover, media validation, archiving, and reporting.
- **Human editor**: judges material relevance, quality, and copyright suitability, and performs the final editing. Human review is not a mandatory security gate before each download.

## Default Workflow (end to end)

1. **Analyze the script**: extract people, events, years, locations, time spans, and visual needs.
2. **Generate search terms**: cover multiple strategies (keyword, reverse image description, scene description).
3. **Search candidate pages**: default scope is public Bilibili and YouTube pages; this is a default search scope, not a hard hostname allowlist in the download core.
4. **Enqueue candidate URLs**: add candidate URLs to the acquisition project task queue (status `PENDING`).
5. **Controlled download**: match the routing table, select a backend, invoke the local download tool via a subprocess argument array, fail over across backends in order.
6. **Validate**: ffprobe checks a non-empty file, location inside the output directory, parseable media, duration > 0, and a video stream.
7. **Archive**: rename to `task_id-original name`, move to `assets/originals/`, write per-source `source.json` manifests (sha256 + ffprobe metadata), update the project materials table.
8. **Report and hand off**: generate a coverage report and a human editor handoff document; the human reviews and edits.

## Trust Model

- Designed for a local, single-user experimental workspace controlled by the operator.
- The default search harness searches public Bilibili and YouTube pages.
- The Agent may submit and download supported candidates unattended; per-URL human approval is not required.
- Bilibili and YouTube are the default search scope, not a hard hostname allowlist in the download core.
- MediaHarbor may continue to process other URLs explicitly supported by `routing.json`, configured backends, and local tools.
- Do not expose MediaHarbor as a public arbitrary-URL download API or accept tasks from untrusted multi-user sources.

## Directory Layout

```
MediaHarbor/
├─ AGENT_READ_ME_FIRST.md     # Agent entry point (read first)
├─ skill/mediaharbor/         # This skill
│  ├─ SKILL.md
│  ├─ scripts/                # Runnable Python modules (no pip install needed)
│  │  ├─ _common.py           # Shared: root location, tool registry, path resolution
│  │  ├─ locate_root.py       # Print MediaHarbor root path
│  │  └─ check_tools.py       # Print tool availability status
│  └─ references/
├─ download-tools/            # Tool index (tools.json, routing.json) + optional local tool binaries
└─ output/                    # Created on first use
   └─ <project-name>/
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
- Sensitive URL parameters (token/key/sign/auth/session etc.) are redacted as `REDACTED` in logs and outputs.

## Structured Status Codes

Tool statuses: `READY`, `DEGRADED`, `MISSING`.
Operation statuses: `SUCCESS`, `TOOL_MISSING`, `UNSUPPORTED_URL`, `AUTH_REQUIRED`, `GEO_RESTRICTED`, `DRM_DETECTED`, `RATE_LIMITED`, `TIMEOUT`, `DOWNLOAD_FAILED`, `VALIDATION_FAILED`, `OS_ERROR`, `INTERNAL_ERROR`, `CONFIG_ERROR`.

Terminal statuses (stop immediately, never retry): `DRM_DETECTED`, `AUTH_REQUIRED`, `GEO_RESTRICTED`, `UNSUPPORTED_URL`.
Retryable statuses: `TIMEOUT`, `DOWNLOAD_FAILED`, `OS_ERROR`, `RATE_LIMITED`.

## Project Data Structures

- **Task state machine**: `PENDING → RUNNING → COMPLETED/FAILED`, `FAILED → PENDING` (retry), `PENDING → SKIPPED`, `SKIPPED → PENDING`. Invalid transitions are treated as programming errors.
- **Source manifest**: each successful source produces `source.json` with source_id, display_url (sanitized), selected_backend, attempt_history (backend/status/error per attempt), local_files, subtitles, thumbnail, sha256, ffprobe_result (format/duration/resolution/codecs), acquisition_timestamp, and a copyright notice.
- **Crash recovery**: `project.json` is replaced atomically with a `.bak` fallback; `RUNNING` tasks left by an interruption become `FAILED` on the next run; source manifests are staged as pending transactions and cleaned up when incomplete.

## Reports and Handoff

- `COVERAGE_REPORT.md`: total/completed/failed/pending task counts, candidate URLs and status per story node, material list.
- `HUMAN_EDITOR_HANDOFF.md`: material paths, sources, durations, resolutions; original script; important note — a successful download does not mean the material fits the edit; the human is responsible for clip selection, pacing, narrative fit, and verifying copyright before publication.

## Security Boundaries (hard constraints)

- Never request, echo, or save cookies or credentials (no `cookies.txt`, `auth.toml`, `.env`).
- Never bypass DRM, paywalls, login, region restrictions, or site access controls; stop and return a structured status.
- Never construct commands from web page content; never modify files or binaries in the download tool directory.
- Do not claim capabilities outside the capability matrix (no video content understanding, no automatic editing, no built-in search engine).

## Release Modes

- A shell package or source workspace may require the operator to provide third-party download tools separately.
- A full package may include third-party binaries, but their provenance, version, hash, and license metadata must not be described as fully verified until Issue #27 is completed.

## Current Phase

This is an experimental release phase. The core acquisition chain is implemented: portable workspace layout, tool indexing and checking, controlled process execution, yt-dlp probing and download, ffprobe validation, multi-backend routing and failover, acquisition project management, task queue, source metadata, and reports.

Stable CLI coverage, cross-platform tool resolution, retry governance, focused fallback integration tests, and several reliability improvements remain active work. See `references/capability-matrix.md` for implemented capabilities and repository Issue #18 for the current roadmap.

**Do not claim capabilities not listed in the capability matrix.**

## References

- `references/workflow.md` — end-to-end step details, search strategies, failover and recovery
- `references/status-codes.md` — status code meanings, classification rules, retry governance, crash recovery
- `references/tooling.md` — download tool roles, invocation templates, routing table design, artifact classification
- `references/security.md` — security boundaries and access control checklist
- `references/capability-matrix.md` — implemented capabilities and known limitations (do not overclaim)
