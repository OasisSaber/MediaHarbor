#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from process_runner import sanitize_url
from ytdlp_adapter import parse_probe_json, probe_url


def main():
    parser = argparse.ArgumentParser(description="Probe URLs with yt-dlp")
    parser.add_argument("urls", nargs="+", help="URLs to probe")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    results = []
    failed = False
    for url in args.urls:
        display_url = sanitize_url(url)
        result = probe_url(url)
        entry = {
            "url": display_url,
            "status": result.status,
            "returncode": result.returncode,
            "elapsed": round(result.elapsed, 2),
        }
        if result.status == "SUCCESS" and result.stdout:
            entry["info"] = parse_probe_json(result.stdout)
        if result.stderr:
            entry["stderr"] = result.stderr[:500]
        results.append(entry)
        if result.status != "SUCCESS":
            failed = True

    if args.json:
        json.dump({"results": results}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for r in results:
            print(f"{r['url']}: {r['status']} ({r.get('elapsed', 0):.1f}s)")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
