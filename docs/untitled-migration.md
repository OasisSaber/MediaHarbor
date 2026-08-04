# Untitled migration

This repository was renamed from MediaHarbor to Untitled.

Compatibility is intentionally source-level rather than package-level: the stable CLI is `python untitled.py`; the Skill lives at `skill/untitled/`; project output data remains schema version 1 unless a separate data migration is approved.

The migration also aligns pip-backed downloader discovery with the active Python interpreter, refreshes expiring execution URLs without duplicating sanitized task identities, and prevents state transition errors from being counted as successful downloads.
