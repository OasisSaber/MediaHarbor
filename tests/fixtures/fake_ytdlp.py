#!/usr/bin/env python3
import json
import sys

if "--dump-json" in sys.argv and "--skip-download" in sys.argv:
    url = (
        [a for a in sys.argv[1:] if a.startswith("http")][0]
        if any(a.startswith("http") for a in sys.argv[1:])
        else "unknown"
    )
    data = {
        "id": "test123",
        "title": "Test Video",
        "ext": "mp4",
        "duration": 30.0,
        "webpage_url": url,
    }
    json.dump(data, sys.stdout)
    sys.exit(0)

sys.exit(1)
