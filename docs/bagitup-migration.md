# BagItUp migration

This repository was renamed from MediaHarbor to Untitled (2026-08-12), and from
Untitled to BagItUp (2026-08-16).

Compatibility is intentionally source-level rather than package-level: the stable
CLI is `python bagitup.py`; the Skill lives at `skill/bagitup/`; project output
data remains schema version 1 unless a separate data migration is approved.

The migration also aligns pip-backed downloader discovery with the active Python
interpreter, refreshes expiring execution URLs without duplicating sanitized task
identities, and prevents state transition errors from being counted as successful
downloads.

## Rename timeline

| Date | Rename | Notes |
|---|---|---|
| 2026-08-12 | MediaHarbor → Untitled | source migration; release identity updated, assets/digest unchanged |
| 2026-08-16 | Untitled → BagItUp | repository rename + CLI/skill/document identity sync |

Old repository URLs redirect to the new ones; do not rely on them long-term.
`tools-manifest.json` points at the direct new URL.
