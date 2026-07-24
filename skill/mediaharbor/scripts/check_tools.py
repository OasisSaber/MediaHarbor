#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from _common import check_tools, load_registry


def main():
    use_json = "--json" in sys.argv
    allow_system_path = "--allow-system-path" in sys.argv
    error = None

    try:
        registry = load_registry()
        result = check_tools(registry, allow_system_path=allow_system_path)
    except Exception as e:
        error = str(e)
        result = None

    if use_json:
        if result is not None:
            output = {
                "status": result.status,
                "platform": result.platform,
                "tools": {
                    name: {
                        "path": t.path,
                        "exists": t.exists,
                        "roles": t.roles,
                        "required": t.required,
                        "source": t.source,
                    }
                    for name, t in result.tools.items()
                },
            }
        else:
            output = {"status": "ERROR", "error": error}

        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(1 if error or (result and result.status == "ERROR") else 0)
    else:
        if error:
            print(f"ERROR: {error}", file=sys.stderr)
            sys.exit(1)
        print(f"Platform: {result.platform}")
        print(f"Status: {result.status}")
        for name, t in result.tools.items():
            mark = "✓" if t.exists else "✗"
            req = "required" if t.required else "optional"
            src = f" [{t.source}]" if t.source else ""
            print(f"  {mark} {name}{src} ({req}): {t.path}")


if __name__ == "__main__":
    main()
