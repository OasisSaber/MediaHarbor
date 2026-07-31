# End-to-End Workflow

## 1. Analyze the Script

Extract from the copy: people (names, identities, on-camera subjects), events (time, place, course of events), years, locations, time spans, and visual needs (historical footage, news footage, b-roll, close-ups, animation, etc.). Output: a structured requirements list used to generate search terms.

## 2. Generate Search Terms

Cover at least three strategies to avoid single-keyword blind spots:

- **Keyword**: combinations of person + event + year (e.g., "Speaker 2024 keynote").
- **Reverse image description**: describe the desired imagery in visual language ("city night aerial shot", "crowd gathering aerial").
- **Scene description**: describe the scene needed per story node; one node can map to multiple candidate URLs.

## 3. Search Candidate Pages

Default search scope: public Bilibili and YouTube pages. This is the default scope of the search harness, not a hard hostname allowlist enforced by the download core.

## 4. Enqueue Candidate URLs

- One acquisition project corresponds to one `project.json` containing story nodes (`story_nodes`), the task queue (`tasks`) and the materials table (`materials`).
- Each story node records title, description, search_terms, candidate_urls; candidate URLs also enter the task queue with status `PENDING`.
- Deduplication: URLs are deduplicated per project by their sanitized form.
- Download parameters (audio stream, quality) are outside the default scope of this workflow; tool defaults apply.

## 5. Controlled Download

Execution order:

1. Load the routing table `routing.json` (regex → ordered backend lists, schema_version=1).
2. No route match → `UNSUPPORTED_URL`; missing or invalid routing table → `CONFIG_ERROR` (a built-in fallback routing table may be used when `safe_fallback` is enabled).
3. Probe the URL with yt-dlp first; live streams switch to streamlink priority.
4. Try backends in routing-table order (max 3 backends), each with its own attempt directory `01-yt-dlp/`, `02-yutto/`.
5. Record each attempt: backend, status, return code, duration, retryable flag, sanitized error.
6. Total attempt count is capped (6); exceeding the cap returns `RATE_LIMITED`.
7. Terminal statuses (DRM/AUTH/GEO/UNSUPPORTED) stop immediately without trying other backends.
8. On success, artifacts land in the attempt directory, awaiting validation and archiving.

### Output Classification

Artifacts are classified by extension: `main` (video), `subtitle` (.srt/.vtt/.ass/.ssa/.lrc), `thumbnail` (.jpg/.jpeg/.png/.webp), `info_json` (.info.json/.nfo). Success without any artifact → `VALIDATION_FAILED`.

## 6. Validation

Each main media file must pass, in order:

1. File exists and is non-empty.
2. File is inside the output directory (paths outside are rejected).
3. ffprobe parses the file (`-show_format -show_streams`).
4. Duration > 0 and a video stream is present.

Any failure → `VALIDATION_FAILED`; the task fails and records the reason.

## 7. Archive

- Move from the attempt directory to `assets/originals/`, renamed `{task_id}-{original file name}`, with a numeric suffix on collision.
- Write `source.json`: source_id, project_id, display_url (sanitized), selected_backend, attempt_history, local_files, subtitles, thumbnail, sha256, ffprobe_result (format_name/duration/size/bit_rate/width/height/video_codec/audio_codec/has_video/has_audio), acquisition_timestamp, copyright notice `Verify copyright before use.`.
- Mark the task `COMPLETED` with backend, output_paths, completion time; the materials table records local_path, sha256, format, duration, resolution, verified=true.
- Archiving uses a "persist then commit" transaction pattern: pending transaction on disk → project completion → commit; on recovery, committed transactions are published and uncommitted ones with their artifacts are cleaned up.

## 8. Reports and Human Handoff

See SKILL.md "Reports and Handoff". Reports refresh automatically after each queue processing round.

## Resilience

- Every task has its own exception boundary: a single task failure does not interrupt the queue.
- `RUNNING` tasks left by an interruption are set to `FAILED` on the next run ("Interrupted before task completion").
- A corrupted `project.json` is restored from the valid `.bak`; writes always go through temp file + `os.replace` atomic replacement.
- Download tool retries follow the route configuration (1-5, default 2).

## Retry Governance

- Retryable statuses retry within a single backend (route max_retries), then move to the next backend.
- Terminal statuses are never retried.
- No fixed backoff is required between retries; all external calls must have timeouts.
