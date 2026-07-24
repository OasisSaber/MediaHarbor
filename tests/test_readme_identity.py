from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"


def _read_first_heading(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def test_readme_identifies_mediaharbor() -> None:
    assert README.is_file(), f"README.md not found at {README}"

    first_heading = _read_first_heading(README)
    assert first_heading == "# MediaHarbor", (
        f"Expected first non-empty line to be '# MediaHarbor', got {first_heading!r}"
    )


def test_readme_does_not_use_agenticwonderwall_template_title() -> None:
    text = README.read_text(encoding="utf-8")

    assert "# AgenticWonderwall" not in text, (
        "README must not contain the template heading '# AgenticWonderwall'"
    )

    assert "AgenticWonderwall 是" not in text, (
        "README must not describe the project as AgenticWonderwall"
    )
