# Download Tools

This directory holds the tool inventory, routing configuration, and the installed tool binaries for MediaHarbor.

**Verified open-source tools are distributed as zip assets of the MediaHarbor GitHub Release** (`tools-windows-x64-v1`). They are not committed to git. Install them with:

```powershell
python scripts/fetch_tools.py
```

The script downloads each zip from the project release, verifies its sha256 against [`tools-manifest.json`](../tools-manifest.json), and extracts it directly into this directory (e.g. `download-tools/yt-dlp/yt-dlp.exe`). Tools without an official standalone Windows binary (yutto, streamlink, gallery-dl) are not shipped as assets; the script prints their pip installation guidance.

## Files

| File | Purpose |
|---|---|
| `tools.json` | Canonical tool inventory: per-tool roles, `required` flags, and Windows x64 relative paths (schema_version=1) |
| `routing.json` | URL routing table: regex patterns → ordered backend lists, `max_retries`, `drm_stop` (schema_version=1) |
| `THIRD_PARTY_NOTICES.md` | Third-party tool licenses and sources |
| `README.md` | This file |
| `<tool>/` | Installed tool binaries (gitignored) |

## Tool Inventory (tools.json)

Current official platform: **Windows x64 only**.

Required tools (shipped as release assets): yt-dlp (probe/vod/playlist/subtitle/metadata), ffmpeg (merge/convert), ffprobe (validate), N_m3u8DL-RE (hls/dash/mss).
Optional tools (no official standalone Windows binary; install via pip per `scripts/fetch_tools.py --tool <name>` guidance): yutto (bilibili), streamlink (live), gallery-dl (social/gallery/post-media).

All paths must be relative — absolute paths, path traversal, and illegal characters are rejected.

## Routing (routing.json)

Routes match URLs in order; the first hit wins. Default routes:

- bilibili: `bilibili\.com` / `b23\.tv` → yt-dlp, yutto
- hls-dash: `\.m3u8` / `\.mpd` → yt-dlp, n-m3u8dl-re
- social: twitter/x/instagram/reddit/tumblr/pixiv → gallery-dl, yt-dlp
- vod: `^https?://` → yt-dlp

Editing the routing table only allows whitelisted backend names and validated regex; invalid entries reject the whole table.

Invocation templates, artifact discovery, and routing semantics are documented in `../skill/mediaharbor/SKILL.md`. Tool update workflow: `../docs/tool-update-process.md`.
