# Tool Update Process

This document describes how Untitled tools are packaged, verified, published, and updated. Tools are hosted as zip assets of the Untitled GitHub Release `tools-windows-x64-v1`; the authoritative inventory is `tools-manifest.json`.

## Principle

- Only **official, open-source, free-to-use** tools are shipped.
- Only tools with an **official standalone Windows binary** are shipped as assets (currently yt-dlp, FFmpeg/ffprobe, N_m3u8DL-RE).
- Tools without one (yutto, streamlink, gallery-dl) are tracked in the manifest with `kind: pip` and installation guidance only.
- Every asset is **sha256-pinned**; fetching is an explicit `scripts/fetch_tools.py` action, never an implicit runtime download.

## Update workflow (when upstream publishes a new version)

1. **Download the new official binary/zip** from upstream (e.g. yt-dlp GitHub release, BtbN FFmpeg-Builds, N_m3u8DL-RE release).
2. **Verify locally on Windows x64**:
   - `yt-dlp.exe --version` and a real probe: `yt-dlp --dump-json --skip-download <public url>`
   - `ffmpeg -version`, `ffprobe -version`, and a real validation pass through Untitled (`python untitled.py run ...`)
   - `N_m3u8DL-RE --version`
   - Run the full validation suite: `powershell -ExecutionPolicy Bypass -File scripts/validate.ps1`
3. **Repackage as a plain zip** laid out relative to `download-tools/` (e.g. `yt-dlp/yt-dlp.exe`, `ffmpeg/ffmpeg.exe` + `ffmpeg/ffprobe.exe` + `ffmpeg/LICENSE.txt`). Include the tool's license file.
4. **Compute the sha256** of the zip and update `tools-manifest.json` (version, archive, sha256, and upstream metadata if changed).
5. **Upload the new zip and a matching `SHA256SUMS.txt`** to the release `tools-windows-x64-v1` (replace the previous asset of the same name, or bump the archive name).
6. **Verify**:
   - `python scripts/fetch_tools.py --verify-manifest` — cross-checks manifest sha256 against the published `SHA256SUMS.txt` (also runs in CI once the release exists)
   - `python scripts/fetch_tools.py --force` on a clean checkout — installs the new versions and reports `check_tools: READY`
7. Update `download-tools/THIRD_PARTY_NOTICES.md` version table if it changed.

## Automation aids

- `python scripts/fetch_tools.py --check-updates` queries upstream GitHub releases and reports whether a newer version exists for each manifest entry (best-effort; FFmpeg builds require manual review).
- CI runs `scripts/fetch_tools.py --verify-manifest`; once the release exists it fails on sha256 drift between the manifest and the published `SHA256SUMS.txt`.

## Releasing (human action)

Creating the `tools-windows-x64-v1` release and uploading assets is a manual, human-authorized release step per the repository workflow (AgenticWonderwall: releases are human-only).
