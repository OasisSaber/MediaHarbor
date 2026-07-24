#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from _common import ensure_output_dir
from process_runner import sanitize_url
from safe_path import resolve_project_dir, validate_project_name
from ytdlp_adapter import download_url, validate_download_result


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
    validated = validate_download_result(result, project_dir)

    display_url = sanitize_url(args.url)

    if args.json:
        output = {
            "url": display_url,
            "project": project_name,
            "status": validated.status,
            "returncode": validated.returncode,
            "elapsed": round(validated.elapsed, 2),
            "attempts": [
                {
                    "n": a.attempt_number,
                    "status": a.status,
                    "retryable": a.retryable,
                    "delay": round(a.delay, 2),
                    "error": a.safe_error,
                }
                for a in validated.attempts
            ],
            "output_dir": str(project_dir),
        }
        if validated.stdout:
            output["stdout"] = validated.stdout[:1000]
        json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(f"URL: {display_url}")
        print(f"Project: {project_name}")
        print(f"Status: {validated.status}")
        print(f"Output: {project_dir}")

    sys.exit(0 if validated.status == "SUCCESS" else 1)


if __name__ == "__main__":
    main()
