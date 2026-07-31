# Download Tools

This directory holds the tool inventory and routing configuration for MediaHarbor. **Do not submit third-party binaries to this repository** — binary tools must be obtained separately and placed in the corresponding subdirectory (e.g., `yt-dlp/yt-dlp.exe`).

## Files

| File | Purpose |
|---|---|
| `tools.json` | Canonical tool inventory: per-tool roles, `required` flags, and Windows x64 relative paths (schema_version=1) |
| `routing.json` | URL routing table: regex patterns → ordered backend lists, `max_retries`, `drm_stop` (schema_version=1) |
| `THIRD_PARTY_NOTICES.md` | Third-party tool licenses and sources |
| `README.md` | This file |

## Tool Inventory (tools.json)

Current official platform: **Windows x64 only**.

Required tools: yt-dlp (probe/vod/playlist/subtitle/metadata), ffmpeg (merge/convert), ffprobe (validate).
Optional tools: yutto (bilibili), streamlink (live), N_m3u8DL-RE (hls/dash/mss), gallery-dl (social/gallery/post-media).

All paths must be relative — absolute paths, path traversal, and illegal characters are rejected.

## Routing (routing.json)

Routes match URLs in order; the first hit wins. Default routes:

- bilibili: `bilibili\.com` / `b23\.tv` → yt-dlp, yutto
- hls-dash: `\.m3u8` / `\.mpd` → yt-dlp, n-m3u8dl-re
- social: twitter/x/instagram/reddit/tumblr/pixiv → gallery-dl, yt-dlp
- vod: `^https?://` → yt-dlp

Editing the routing table only allows whitelisted backend names and validated regex; invalid entries reject the whole table.

Invocation templates, artifact discovery, and routing semantics are documented in `../skill/mediaharbor/SKILL.md`.
