# Third-Party Notices

BagItUp works with the following third-party tools. Tools with an official standalone Windows binary are distributed as zip assets of the BagItUp release `tools-windows-x64-v1`; others are installed via pip. All tools are open source and free to use.

## Downloader Tools

| Tool | Version (manifest) | License | Repository |
|------|--------------------|---------|------------|
| yt-dlp | 2026.07.04 | Unlicense | https://github.com/yt-dlp/yt-dlp |
| FFmpeg / ffprobe | n8.1.2-34-g9b6c8969e0 (2026-07-31 build) | LGPL-2.1+ | https://github.com/BtbN/FFmpeg-Builds |
| yutto | 2.2.0 | GPL-3.0 | https://github.com/yutto-dev/yutto |
| Streamlink | 8.4.0 | BSD 2-Clause | https://github.com/streamlink/streamlink |
| N_m3u8DL-RE | v0.6.0-beta | MIT | https://github.com/nilaoda/N_m3u8DL-RE |
| gallery-dl | 1.32.8 | GPLv2 | https://github.com/mikf/gallery-dl |

## Distribution

- Shipped as release assets (zip, sha256-pinned): yt-dlp, FFmpeg/ffprobe, N_m3u8DL-RE. Each zip carries its license file alongside the binaries.
- Installed via pip (no official standalone Windows binary): yutto, Streamlink, gallery-dl. See `scripts/fetch_tools.py --tool <name>` for guidance.
- The authoritative version, sha256, and upstream metadata live in `tools-manifest.json`.

## Usage

Run `python scripts/fetch_tools.py` to fetch the shipped tools into `download-tools/`. BagItUp never downloads, installs, or upgrades tools implicitly at runtime; fetching is an explicit script action.

## License BagItUp

BagItUp itself is licensed under the MIT License. See `../LICENSE`.
