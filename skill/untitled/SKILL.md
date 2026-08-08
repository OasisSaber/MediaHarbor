---
name: untitled
description: Collect video editing materials for an existing script with Untitled: analyze the script for people, events, years, locations and visual needs, generate search terms, search candidate video pages, enqueue candidates, download through controlled local tools, validate with ffprobe, archive, and hand off to a human editor. Trigger when the user provides a script or copy and asks to find, download, or collect video materials, or explicitly activates Untitled.
---

# Untitled Skill

## Trigger

The human provides an existing script or text and asks to find matching video materials, or explicitly activates Untitled for material collection.

## Scope and Installation

- Untitled is a local, single-user, Windows x64-first Agent Skill source repository.
- Current official platform: Windows x64 only.
- Runtime requirements: Windows x64, Python 3.11+, and local third-party tools configured by `download-tools/tools.json` and `tools-manifest.json`.
- Deployment: clone the complete repository into the Agent workspace. Untitled itself has no package installation or build step.
- The stable Agent-facing CLI is `python untitled.py` from the repository root.
- Internal scripts under `skill/untitled/scripts/` are compatibility and implementation entry points, not a stable public API.
- ZIP-backed tools are fetched only by the explicit `python scripts/fetch_tools.py` action. Untitled core never downloads or upgrades tools implicitly during task processing.
- Python-module tools such as yutto, streamlink, and gallery-dl are resolved in the active interpreter and invoked as `[sys.executable, "-m", module]`.

## Roles

- **Agent**: understands the supplied script, generates search terms, searches and filters candidate pages, submits tasks, organizes results, and reports coverage.
- **Untitled core**: checks tools, probes candidates, invokes controlled subprocesses, applies bounded fallback, validates media, archives artifacts, persists state, and generates reports.
- **Human editor**: judges relevance, narrative fit, quality, and copyright suitability, and performs final editing. A successful download is not editorial approval.

## Default Workflow

1. Analyze the script for people, events, years, locations, time spans, and visual needs.
2. Generate multiple search strategies: direct keywords, scene descriptions, and reverse-description terms.
3. Search public candidate pages. Bilibili and YouTube are the default search scope, not a hard core hostname allowlist.
4. Probe and score candidates. Record metadata, provenance score, state, and rejection reasons.
5. Enqueue accepted candidates. An explicit override may enqueue a rejected or failed-probe candidate while preserving its prior evidence.
6. Match the routing table and invoke a bounded backend sequence.
7. Validate downloaded main media with ffprobe.
8. Evaluate the configured quality profile and local visual-contamination heuristics.
9. Move final artifacts into `assets/originals/`, record hashes and source metadata, and commit project state.
10. Generate coverage and human-editor handoff reports.

## Trust Model

- Designed for an operator-controlled local single-user workspace.
- The Agent may submit supported candidates without per-URL human approval.
- Do not expose Untitled as a public arbitrary-URL download API or accept tasks from untrusted multi-user sources.
- Other URLs are processed only when supported by `download-tools/routing.json`, configured backends, and locally available tools.

## Directory Layout

```text
Untitled/
|-- AGENT_READ_ME_FIRST.md
|-- untitled.py
|-- skill/untitled/
|   |-- SKILL.md
|   `-- scripts/
|-- download-tools/
|   |-- tools.json
|   `-- routing.json
|-- scripts/
|-- tests/
`-- output/
    `-- <project-name>/
        |-- project.json
        |-- input/
        |-- planning/
        |-- acquisition/
        |   `-- sources/
        |-- assets/
        |   `-- originals/
        |-- logs/
        `-- reports/
```

Project names must be safe: no path separators, path traversal, Windows reserved names, illegal Windows filename characters, or control characters; maximum length is 128 characters.

## Tool Distribution and Check

Before downloading, verify the published tool inventory:

```bash
python scripts/fetch_tools.py --verify-manifest
```

`tools-manifest.json` contains a boolean `release_required` field:

- `true`: `SHA256SUMS.txt` and every declared ZIP asset must exist and match the manifest. HTTP errors, missing assets, and checksum drift fail verification.
- `false`: remote verification is intentionally skipped and only structural validation is performed. This is allowed only for a clearly documented pre-publication state.

Fetch ZIP-backed tools explicitly:

```bash
python scripts/fetch_tools.py
```

Check runtime availability:

```bash
python untitled.py check-tools
python skill/untitled/scripts/check_tools.py --json
```

Required tools:

- yt-dlp: probing, VOD, subtitles, and metadata.
- ffmpeg: merging, conversion, and local visual sampling.
- ffprobe: downloaded-media validation.

Optional tools:

- yutto: Bilibili-specialized backend.
- streamlink: live-stream backend.
- N_m3u8DL-RE: HLS, DASH, and MSS backend.
- gallery-dl: social and gallery backend.

The fetcher validates normalized forward-slash member paths, rejects cross-tool archive or destination collisions and duplicate declared ZIP members, downloads assets into a temporary directory, validates SHA-256 before extraction, extracts only declared members into private staging, and installs staged files transactionally. A complete rollback removes its temporary backup; an incomplete rollback preserves the backup and reports its path.

## Controlled Subprocess Rules

- Invoke commands with argument arrays only. Never use `shell=True`.
- Never construct commands from arbitrary titles, descriptions, comments, or other page content.
- External calls have finite timeouts and bounded retries.
- Subprocess text decoding uses UTF-8 with replacement for invalid byte sequences.
- Captured backend stderr is bounded before persistence or reporting.
- Raw execution URLs are used only for probe, routing, and download.
- Logs, reports, project display fields, and Agent-facing output use sanitized display URLs.
- Sensitive query or fragment keys such as token, key, secret, signature, auth, session, credential, password, expires, and expiry are redacted.

## Status Codes

Tool statuses: `READY`, `DEGRADED`, `MISSING`.

Operation statuses:

- `SUCCESS`
- `TOOL_MISSING`
- `UNSUPPORTED_URL`
- `AUTH_REQUIRED`
- `GEO_RESTRICTED`
- `DRM_DETECTED`
- `RATE_LIMITED`
- `TIMEOUT`
- `DOWNLOAD_FAILED`
- `VALIDATION_FAILED`
- `OS_ERROR`
- `INTERNAL_ERROR`
- `CONFIG_ERROR`

Within one backend, terminal statuses are not retried. Cross-backend fallback stops immediately for DRM, authentication, and geographic restriction failures. An unsupported result may fall through to another backend configured for the same route.

## Error Classification

Classification priority:

1. Return code 0 -> `SUCCESS`.
2. Widevine, PlayReady, FairPlay, or explicit encrypted DRM evidence -> `DRM_DETECTED`.
3. HTTP 401, sign-in, login-required, or private-video evidence -> `AUTH_REQUIRED`.
4. Geographic restriction evidence -> `GEO_RESTRICTED`.
5. HTTP 429 or rate-limit evidence -> `RATE_LIMITED`.
6. Unsupported URL or no video format evidence -> `UNSUPPORTED_URL`.
7. Other non-zero return codes -> `DOWNLOAD_FAILED`.
8. Timeout -> `TIMEOUT`; missing executable -> `TOOL_MISSING`; other OS failures -> `OS_ERROR`.

## Retry and Recovery

- Each route defines a bounded retry count from 1 to 5; default is 2.
- A route selects at most a bounded number of backends; default is 3.
- `MAX_TOTAL_ATTEMPTS` enforces a global cross-backend attempt budget.
- Retryable failures use bounded exponential backoff.
- `project.json` is written atomically and retains a `.bak` fallback.
- `RUNNING` tasks left by an interrupted process become `FAILED` on the next run.
- Multi-file finalization attempts rollback when a move fails partway.
- Source manifests are staged as `<task_id>.source.pending` transactions and committed after task completion.
- Recovery publishes pending source transactions for completed tasks and removes uncommitted transactions and their controlled artifacts.
- A task-state transition error is counted as recovered success only when the persisted task is `COMPLETED`, has recorded output paths, and every recorded output exists. Otherwise it remains an internal failure requiring reconciliation.

## Candidate and URL Identity

Each candidate stores separate values for:

- `execution_url`: raw URL used for probe and download.
- `display_url`: sanitized identity used in state, logs, reports, and Agent output.

When a new signed URL sanitizes to an existing candidate identity:

- Pending, failed, and skipped work may refresh the raw execution URL without creating a duplicate task.
- Completed work is not reopened.
- Previous probe failures, rejection reasons, and override evidence remain auditable.

Complete format arrays, direct media URLs, cookies, and request headers are not persisted.

## Project Data Structures

- **Task state machine**: `PENDING -> RUNNING -> COMPLETED/FAILED`, `FAILED -> PENDING`, `PENDING -> SKIPPED`, and `SKIPPED -> PENDING`.
- **Story nodes**: narrative units with title, description, search terms, and candidate URL associations.
- **Candidate**: sanitized and execution URL identity, platform metadata, probe state, provenance score, reasons, optional story-node association, and override evidence.
- **Source manifest**: source identity, sanitized URL, selected backend, bounded attempt history, local files, subtitles, thumbnail, SHA-256, ffprobe result, acquisition timestamp, and rights reminder.
- **Material assessment**: separate technical, quality, and editorial states with reason lists and assessment timestamp.
- **Quality profile**: preferred and minimum media properties used for pre-download selection and post-download evaluation.
- **Visual contamination analysis**: bounded local frame sampling and deterministic heuristics for persistent subtitles, likely watermarks, text-heavy material, and multi-panel or commentary layouts.

## Reports and Handoff

- `COVERAGE_REPORT.md`: candidate and task coverage by story node, plus material assessment grouping.
- `HUMAN_EDITOR_HANDOFF.md`: paths, sources, media properties, assessments, story nodes, original script, and human-review reminders.

Reports refresh after each queue-processing round.

## Security Boundaries

- Never request, echo, or save cookies or credentials.
- Never bypass DRM, paywalls, login requirements, region restrictions, or access controls.
- Never modify installed binaries during normal task processing.
- Never claim built-in search, semantic video understanding, automatic editing, or automatic rights clearance.
- Treat visual analysis as a local heuristic, not content understanding.

## Current Reliability Limits

- Official platform support remains Windows x64 only.
- Release availability and third-party site behavior can interrupt cold start or downloads.
- Python-module tools must be installed into the same interpreter used to run Untitled.
- There is no cross-process project lock; do not run multiple writers against the same project concurrently.
- Credential redaction is defense in depth and may not recognize every possible structured or bearer-token representation.
- Visual analysis may produce false positives or false negatives and never substitutes for human review.
- Project output data remains schema version 1; no data migration is implied by the Untitled source rename.
- `drm_stop` remains part of routing schema compatibility; current runtime hard-stops DRM, authentication, and geographic restriction failures.

## Agent-Facing CLI

Run `python untitled.py` from the repository root.

Commands:

- `check-tools`
- `project-create <name>`
- `story-node-add <project> <title> [--description <text>]`
- `story-node-list <project>`
- `candidate-add <project> <url>`
- `process <project>`
- `status <project>`
- `run --project <name> --url <url>`

All commands return the fixed top-level JSON fields `ok`, `status`, `data`, and `error`.

## Internal Entry Points

| Script | Purpose |
|---|---|
| `locate_root.py` | Locate the Untitled workspace root. |
| `check_tools.py` | Report runtime tool availability. |
| `orchestrator.py` | Process the queue: download -> validate -> assess -> archive -> report. |
| `router.py` | Match routes and apply bounded backend fallback. |
| `probe.py` | Internal yt-dlp probe diagnostic. |
| `download.py` | Legacy internal single-URL helper. |
| `_common.py` | Tool registry and binary or Python-module command resolution. |
| `acquisition.py` | Candidate, task, and material state operations. |
| `project.py` | Project schema and atomic persistence. |
| `process_runner.py` | Controlled process execution, classification, retry, and redaction. |

## Current Status

Untitled is in an experimental release-candidate preparation phase. The core acquisition chain is implemented and tested. A release candidate additionally requires strict published-asset verification, a clean Windows x64 cold-start run, full validation, a real public-sample end-to-end drill, and an independent Code Review with no merge-blocking findings.
