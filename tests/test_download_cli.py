from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "bagitup" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_download_cli_imports():
    from download import main

    assert callable(main)
