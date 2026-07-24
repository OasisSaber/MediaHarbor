from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "mediaharbor" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def setup_temp_root(dst: Path) -> None:
    (dst / "AGENT_READ_ME_FIRST.md").write_text("")
    (dst / "download-tools").mkdir(parents=True, exist_ok=True)
    (dst / "skill" / "mediaharbor").mkdir(parents=True, exist_ok=True)
    (dst / "skill" / "mediaharbor" / "SKILL.md").write_text(
        "---\ntitle: test\n---\n", encoding="utf-8"
    )
    (dst / "skill" / "mediaharbor" / "scripts").mkdir(parents=True, exist_ok=True)


def copy_scripts_to(dst: Path) -> None:
    src = Path(__file__).resolve().parent.parent / "skill" / "mediaharbor" / "scripts"
    scripts_dir = dst / "skill" / "mediaharbor" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for fname in ["_common.py", "check_tools.py"]:
        (scripts_dir / fname).write_text(
            (src / fname).read_text(encoding="utf-8"), encoding="utf-8"
        )
