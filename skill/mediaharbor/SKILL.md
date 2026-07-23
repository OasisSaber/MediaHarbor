---
name: mediaharbor
description: Use MediaHarbor to collect video editing materials from an existing script by planning searches, submitting candidate URLs, invoking local download tools, validating media, and organizing outputs inside the portable MediaHarbor workspace.
---

## Trigger

Human provides an existing script or text and asks to find matching video materials, OR human explicitly activates MediaHarbor for material collection.

## Responsibilities

1. Read and analyze the script to extract people, events, years, locations, and visual needs.
2. Generate search terms across multiple strategies (keyword, reverse image, scene description).
3. Search the internet for candidate video pages (this is Agent responsibility, not MediaHarbor).
4. Submit candidate URLs to MediaHarbor's download queue.
5. Invoke local download tools through controlled subprocess calls.
6. Validate downloaded media with ffprobe.
7. Rename, organize, and generate a material manifest.
8. Hand off to human editor.

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
├─ download-tools/            # Tool index (tools.json) + tool binaries
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

## Security

- All external tools are invoked via subprocess with argument arrays (no `shell=True`).
- Never construct commands from web page titles, descriptions, or comments.
- Tool retry count is limited.
- DRM detection stops processing.
- Login-gated content returns `AUTH_REQUIRED`.
- Never request, echo, or save cookies or credentials.

## Error Handling

Structured status values:
- `READY` — tool available
- `UNSUPPORTED` — URL protocol not supported
- `AUTH_REQUIRED` — login required
- `GEO_RESTRICTED` — region blocked
- `DRM_DETECTED` — protected content
- `RATE_LIMITED` — rate limited
- `DOWNLOAD_FAILED` — general failure

## Current Phase

This is the **initial release phase**. All planned capabilities are implemented: portable workspace layout, tool indexing and checking, controlled process execution, yt-dlp probing and download, ffprobe validation, multi-backend routing and failover, acquisition project management with task queue and reports, and Release assembly with end-to-end isolation verification. See references/capability-matrix.md for details.

**Do not claim capabilities not listed in the capability matrix.**
