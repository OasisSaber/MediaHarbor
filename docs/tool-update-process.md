# Tool Update and Release Process

This document defines how BagItUp's Windows x64 tools are packaged, verified, published, and updated. `tools-manifest.json` is authoritative.

## Distribution Rules

- Ship only official, open-source, free-to-use tools.
- Ship ZIP assets only for tools with an official standalone Windows binary.
- Track yutto, streamlink, and gallery-dl as `kind: pip`; install them explicitly into the active Python interpreter.
- Pin every ZIP by SHA-256.
- Never download tools implicitly during normal BagItUp task processing.
- Treat GitHub repository rename and Release migration as separately authorized operations.

## Manifest Release State

`tools-manifest.json` must contain:

```json
"release_required": true
```

Use `true` when README and installation instructions describe the Release as usable. In this mode:

- Missing `SHA256SUMS.txt` fails.
- HTTP errors fail.
- Missing ZIP assets fail.
- Checksum drift fails.

`release_required: false` is permitted only for an explicitly documented pre-publication branch. It must not be merged while the normal installation path claims that Release assets are available.

## Update Workflow

1. Download official upstream binaries or archives.
2. Verify locally on Windows x64:
   - `yt-dlp.exe --version` and a real public-page probe.
   - `ffmpeg -version` and `ffprobe -version`.
   - A real BagItUp media validation pass.
   - `N_m3u8DL-RE --version`.
3. Repackage ZIPs relative to `download-tools/` and include license files.
4. Compute each ZIP SHA-256 and update version, archive, hash, license, upstream, and `provides` fields in `tools-manifest.json`.
5. Place candidate release assets in a local directory.
6. Validate and generate checksums:

   ```powershell
   python scripts/prepare_release_assets.py --asset-dir <directory>
   ```

7. Obtain explicit human authorization to create or modify the Release.
8. Upload the ZIP assets and generated `SHA256SUMS.txt` to `tools-windows-x64-v1`.
9. Verify the published Release:

   ```powershell
   python scripts/fetch_tools.py --verify-manifest
   ```

10. Use a clean Windows x64 clone to run:

    ```powershell
    python scripts/fetch_tools.py
    python bagitup.py check-tools
    powershell -ExecutionPolicy Bypass -File scripts/cold_start_smoke.ps1
    ```

11. Run the full repository validation and independent Code Review.

## Repository Rename Sequence

Before the GitHub repository is renamed, the Release URL must reference the current real repository. After the human-authorized rename:

1. Confirm default branch, Rulesets, required checks, permissions, Issues, PRs, and Release assets are intact.
2. Update `release_base_url` to the new direct repository URL.
3. Search the repository for the old owner/repository path.
4. Verify the new URL directly; do not accept success that depends only on an old-URL redirect.
5. Run strict Manifest verification and the Windows cold-start smoke again.

## CI Contract

CI runs:

```bash
python scripts/fetch_tools.py --verify-manifest
```

A published Release failure is a real CI failure. Do not catch 404 or network errors and silently convert them into a structural-only pass.

## Human-Only Actions

The following require explicit authorization under TheMasterplan workflow:

- Rename the GitHub repository.
- Create, modify, replace, or delete a Release or Release asset.
- Create, move, or delete a Tag.
- Merge the final PR.
- Force-push or rewrite remote history.

## Manifest and archive safety rules

- Archive names and `provides` paths use normalized forward slashes only. Backslashes,
  absolute paths, empty components, `.`/`..`, control characters, and Windows-invalid
  path characters are rejected before download or extraction.
- Archive file names must be unique across all zip-backed tools. Declared installation
  destinations must also be unique across tools; one tool may not overwrite another.
- Every declared ZIP member must occur exactly once. Missing or duplicate members fail
  validation before any installation write.
- Installation is transactional. Existing files are moved to a private backup directory,
  staged files are installed, and failures trigger rollback. When rollback itself is
  incomplete, the backup directory is preserved and its path is reported for manual
  recovery; the last recoverable copy is never deleted silently.
