#!/usr/bin/env python3
# Legacy / internal entry point.
# Kept until Issue #29 (unified agent-facing CLI) replaces it. Not part of the
# normal skill workflow; prefer the acquisition project workflow (orchestrator).
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import ensure_output_dir
from ffprobe_validator import validate_downloaded_file
from process_runner import sanitize_url
from safe_path import resolve_project_dir, validate_project_name
from ytdlp_adapter import download_url


def main():
    parser = argparse.ArgumentParser(description="Download media from a URL")
    parser.add_argument("url", help="URL to download")
    parser.add_argument("--project", "-p", default="default", help="Project name")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    project_name = validate_project_name(args.project)
    output_base = ensure_output_dir()
    project_dir = resolve_project_dir(output_base, project_name)

    result = download_url(args.url, project_dir)
    if result.status == "SUCCESS":
        media_types = result.metadata.get("media_types", {})
        main_paths = media_types.get("main") or result.output_paths
        if not main_paths or any(
            validate_downloaded_file(Path(path), project_dir).status != "SUCCESS"
            for path in main_paths
        ):
            result.status = "VALIDATION_FAILED"

    display_url = sanitize_url(args.url)

    if args.json:
        output = {
            "url": display_url,
            "project": project_name,
            "status": result.status,
            "output_paths": [str(path) for path in result.output_paths],
            "attempts": [
                {
                    "n": a.attempt_number,
                    "status": a.status,
                    "retryable": a.retryable,
                    "error": a.safe_error,
                }
                for a in result.attempts
            ],
            "output_dir": str(project_dir),
        }
        json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(f"URL: {display_url}")
        print(f"Project: {project_name}")
        print(f"Status: {result.status}")
        print(f"Output: {project_dir}")

    sys.exit(0 if result.status == "SUCCESS" else 1)


if __name__ == "__main__":
    main()
