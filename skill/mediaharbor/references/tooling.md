# Download Tools and Routing

## Tool Roles

| Tool | Role | Required |
|---|---|---|
| yt-dlp | Default probing, VOD, playlists, subtitles, metadata | yes |
| ffmpeg | Merge, convert | yes |
| ffprobe | Post-download validation | yes |
| yutto | Bilibili backup download | no |
| streamlink | Live streams | no |
| N_m3u8DL-RE | HLS, DASH, MSS | no |
| gallery-dl | Social posts, galleries, media collections | no |

Primary platform is Windows x64; Linux/macOS paths are best-effort placeholders.

## Invocation Templates

Each backend tool is invoked through a fixed argument template (always an argument array), never arbitrary command construction:

| Tool | Template (argument array) |
|---|---|
| yt-dlp probe | `--no-playlist --dump-json --skip-download <url>` |
| yt-dlp download | `--no-playlist --format bv*+ba/b -o <dir>/%(extractor)s-%(id)s.%(ext)s --print after_move:filepath --write-info-json --write-thumbnail --write-subs --write-auto-subs --no-overwrites [--ffmpeg-location <dir>] <url>` |
| yutto | `<url> -d <output_dir>` |
| streamlink | `<url> best -o <output_dir>/stream.ts` |
| N_m3u8DL-RE | `<url> --save-dir <output_dir>` |
| gallery-dl | `<url> -d <output_dir>` |

Artifact discovery: snapshot the output directory before and after download (mtime+size fingerprint); only new or changed files count as artifacts of this run. Output files are classified by extension into main / subtitle / thumbnail / info_json.

## Routing Table (routing.json)

- schema_version=1; entries carry name, patterns (regex list), backends (ordered list limited to yt-dlp/yutto/streamlink/n-m3u8dl-re/gallery-dl), max_retries (1-5), drm_stop.
- Routes are matched in order with case-insensitive regex search; the first hit applies.
- Built-in fallback routes (used when routing.json is missing/invalid and safe_fallback is enabled):
  - bilibili: `bilibili\.com|b23\.tv` → yt-dlp, yutto
  - hls-dash: `\.m3u8|\.mpd` → yt-dlp, n-m3u8dl-re
  - social: twitter/x/instagram/reddit/tumblr/pixiv → gallery-dl, yt-dlp
  - vod: `^https?://` → yt-dlp
- Live detection: when the yt-dlp probe reports is_live or live_status is_live/is_upcoming, the live route applies (streamlink, yt-dlp).
- Editing the routing table only allows whitelisted backend names and validated regex; invalid entries reject the whole table (or degrade to fallback routes).

## Artifacts and Output Directories

- Each backend's attempt artifacts land in `<project>/assets/.staging/<task_id>/NN-<backend>/`; after validation they move into `assets/originals/` renamed `{task_id}-{original name}`.
- The final directory contains only validated media; staging directories and failed artifacts are cleaned up when the task ends.
