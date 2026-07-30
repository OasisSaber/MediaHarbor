---
name: mediaharbor
description: Use MediaHarbor to collect video editing materials from an existing script by planning searches, submitting candidate URLs, invoking local download tools, validating media, and organizing outputs inside the portable MediaHarbor workspace.
---

## Trigger

Human provides an existing script or text and asks to find matching video materials, OR human explicitly activates MediaHarbor for material collection.

## Responsibilities

1. Read and analyze the script to extract people, events, years, locations, and visual needs.
2. Generate search terms across multiple strategies (keyword, reverse image, scene description).
3. Search the internet for candidate video pages (this is Agent / Harness responsibility, not MediaHarbor core responsibility).
4. Submit candidate URLs to MediaHarbor's download queue.
5. Invoke local download tools through controlled subprocess calls.
6. Validate downloaded media with ffprobe.
7. Rename, organize, and generate a material manifest.
8. Hand off to the human editor for relevance, quality, copyright, and final editing decisions.

## Default Workflow and Trust Model

- MediaHarbor is designed for a local, single-user experimental workspace controlled by the operator.
- The default search Harness searches public Bilibili and YouTube pages.
- The Agent may submit and download supported candidates unattended. Per-URL human approval is not required.
- Bilibili and YouTube are the default search scope, not a hard hostname allowlist in the download core.
- MediaHarbor may continue to process other URLs explicitly supported by `routing.json`, configured backends, and local tools.
- Human review is for material relevance, quality, copyright suitability, and final editing; it is not a mandatory security gate before each download.
- Do not expose MediaHarbor as a public arbitrary-URL download API or accept tasks from untrusted multi-user sources under this trust model.

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
├─ download-tools/            # Tool index (tools.json) + optional local tool binaries
│  ├─ tools.json
│  └─ README.md
└─ output/                    # Created on first use
   └─ <project-name>/
```

## Tool Check

Before downloading, run:

```bash
python skill/mediaharbor/scripts/check_tools.py --json
```

Returns `READY`, `DEGRADED`, or missing tool status.

## Security and Access Boundaries

- All external tools are invoked via subprocess with argument arrays (no `shell=True`).
- Never construct commands from web page titles, descriptions, or comments.
- Tool retry count is limited.
- DRM detection stops processing.
- Login-gated content returns `AUTH_REQUIRED`.
- Never request, echo, or save cookies or credentials.
- Do not bypass DRM, authentication, paywalls, region restrictions, or site access controls.
- Do not add a mandatory per-URL confirmation step for normal supported public-page downloads in the local single-user workflow.

## Error Handling

Structured status values include:

- `READY` — tool available
- `UNSUPPORTED_URL` — URL or route not supported
- `AUTH_REQUIRED` — login required
- `GEO_RESTRICTED` — region blocked
- `DRM_DETECTED` — protected content
- `RATE_LIMITED` — rate limited
- `DOWNLOAD_FAILED` — general failure

## Release Modes

- A shell package or source workspace may require the operator to provide third-party download tools separately.
- A full package may include third-party binaries, but their provenance, version, hash, and license metadata must not be described as fully verified until Issue #27 is completed.

## Current Phase

This is an experimental release phase. The core acquisition chain is implemented: portable workspace layout, tool indexing and checking, controlled process execution, yt-dlp probing and download, ffprobe validation, multi-backend routing and failover, acquisition project management, task queue, source metadata, and reports.

Stable CLI coverage, cross-platform tool resolution, retry governance, focused fallback integration tests, and several reliability improvements remain active work. See `references/capability-matrix.md` for implemented capabilities and repository Issue #18 for the current roadmap.

**Do not claim capabilities not listed in the capability matrix.**
