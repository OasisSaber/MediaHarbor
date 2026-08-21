# Third-Party Notices

BagItUp works with the following third-party tools. Tools with an official standalone Windows binary are distributed as zip assets of the BagItUp release `tools-windows-x64-v1`; others are installed via pip. All tools are open source and free to use.

## Downloader Tools

| Tool | Version (manifest) | License | Repository |
|------|--------------------|---------|------------|
| yt-dlp | 2026.07.04 | Unlicense | https://github.com/yt-dlp/yt-dlp |
| FFmpeg / ffprobe | n8.1.2-34-g9b6c8969e0 (2026-07-31 build) | LGPL-3.0-or-later (artifact) | https://github.com/BtbN/FFmpeg-Builds |
| yutto | 2.2.0 | GPL-3.0 | https://github.com/yutto-dev/yutto |
| Streamlink | 8.4.0 | BSD 2-Clause | https://github.com/streamlink/streamlink |
| N_m3u8DL-RE | v0.6.0-beta | MIT | https://github.com/nilaoda/N_m3u8DL-RE |
| gallery-dl | 1.32.8 | GPLv2 | https://github.com/mikf/gallery-dl |

## Distribution

- Shipped as release assets (zip, sha256-pinned): yt-dlp, FFmpeg/ffprobe, N_m3u8DL-RE. Each zip carries its license file alongside the binaries.
- Installed via pip (no official standalone Windows binary): yutto, Streamlink, gallery-dl. See `scripts/fetch_tools.py --tool <name>` for guidance.
- The authoritative version, sha256, and upstream metadata live in `tools-manifest.json`.

### FFmpeg release audit

The `tools-windows-x64-v1` FFmpeg asset was physically inspected on 2026-08-21. Its
archive digest matches the manifest, and both executables report
`n8.1.2-34-g9b6c8969e0-20260731` with `--enable-version3`; the bundled `LICENSE.txt`
is the GNU LGPL v3 text. The manifest therefore records the artifact as
`LGPL-3.0-or-later`, rather than implying that the shipped build is only LGPL 2.1+.

The asset currently contains no FFmpeg source snapshot, build-recipe/commit record,
or source-offer document. License closure for a future release remains blocked until
the corresponding source and build provenance are published or linked, together with
the applicable notices for enabled components. See
[`docs/ffmpeg-release-audit-2026-08-21.md`](../docs/ffmpeg-release-audit-2026-08-21.md)
for the evidence and release follow-up checklist.

## Usage

Run `python scripts/fetch_tools.py` to fetch the shipped tools into `download-tools/`. BagItUp never downloads, installs, or upgrades tools implicitly at runtime; fetching is an explicit script action.

## License BagItUp

BagItUp itself is licensed under the MIT License. See `../LICENSE`.

