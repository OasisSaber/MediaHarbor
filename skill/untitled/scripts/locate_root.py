#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from _common import find_project_root, get_paths


def main():
    use_json = "--json" in sys.argv
    error = None

    try:
        root = find_project_root()
        paths = get_paths()
    except RuntimeError as e:
        root = None
        error = str(e)

    if use_json:
        output = {"root": str(root) if root else None, "error": error}
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(1 if error else 0)
    else:
        if error:
            print(error, file=sys.stderr)
            sys.exit(1)
        print(str(root))
        print(f"output: {paths['output']}")


if __name__ == "__main__":
    main()
