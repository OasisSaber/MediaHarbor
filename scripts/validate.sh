#!/bin/bash
# Technical validation for AgenticWonderwall.
#
# Verifies exactly four checks:
#   1. Internal Markdown links
#   2. Committed mode of Shell scripts
#   3. YAML syntax
#   4. Shell syntax

set -o pipefail

FAILED=0
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR" || exit 1

PYTHON=""
if python3 -c "import sys" >/dev/null 2>&1; then
    PYTHON="python3"
elif python -c "import sys" >/dev/null 2>&1; then
    PYTHON="python"
fi

echo "=== Validation ==="
echo ""

# ---- Check 1: Internal Markdown links ----
echo "--- Check 1: Internal Markdown links ---"
if [ -z "$PYTHON" ]; then
    echo "  UNAVAILABLE: Python is required for Markdown link validation."
    FAILED=$((FAILED + 1))
elif "$PYTHON" - "$REPO_DIR" <<'PY'
import html
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(sys.argv[1]).resolve()
excluded_dirs = {
    ".git",
    ".jj",
    "node_modules",
    ".venv",
    "venv",
    ".cache",
    "__pycache__",
}
broken = []


def normalize_label(value: str) -> str:
    return " ".join(value.strip().lower().split())


def strip_code(markdown: str) -> str:
    output = []
    fence_char = None
    fence_length = 0

    for line in markdown.splitlines(keepends=True):
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence_char is not None:
            if fence and fence.group(1)[0] == fence_char and len(fence.group(1)) >= fence_length:
                fence_char = None
                fence_length = 0
            output.append("\n" if line.endswith("\n") else "")
            continue
        if fence:
            fence_char = fence.group(1)[0]
            fence_length = len(fence.group(1))
            output.append("\n" if line.endswith("\n") else "")
            continue
        if line.startswith("    ") or line.startswith("\t"):
            output.append("\n" if line.endswith("\n") else "")
            continue

        result = []
        index = 0
        while index < len(line):
            if line[index] != "`":
                result.append(line[index])
                index += 1
                continue
            run_end = index
            while run_end < len(line) and line[run_end] == "`":
                run_end += 1
            marker = line[index:run_end]
            close = line.find(marker, run_end)
            if close == -1:
                result.append(marker)
                index = run_end
            else:
                result.append(" " * (close + len(marker) - index))
                index = close + len(marker)
        output.append("".join(result))

    return "".join(output)


def find_closing(text: str, start: int, opening: str, closing: str):
    depth = 1
    index = start
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == opening:
            depth += 1
        elif text[index] == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def destination_from_parentheses(content: str):
    content = content.strip()
    if not content:
        return ""
    if content.startswith("<"):
        end = content.find(">", 1)
        return content[1:end] if end != -1 else None

    depth = 0
    escaped = False
    destination = []
    for character in content:
        if escaped:
            destination.append(character)
            escaped = False
            continue
        if character == "\\":
            escaped = True
            destination.append(character)
            continue
        if character == "(":
            depth += 1
        elif character == ")" and depth > 0:
            depth -= 1
        elif character.isspace() and depth == 0:
            break
        destination.append(character)
    return "".join(destination)


def markdown_targets(text: str):
    definitions = {}
    for match in re.finditer(r"(?m)^ {0,3}\[([^\]]+)\]:\s*(?:<([^>]+)>|(\S+))", text):
        definitions[normalize_label(match.group(1))] = match.group(2) or match.group(3)

    targets = []
    explicit_references = []
    shortcut_references = []
    index = 0
    while index < len(text):
        image = text.startswith("![", index)
        if text[index] != "[" and not image:
            index += 1
            continue
        bracket = index + 1 if image else index
        backslashes = 0
        escape_index = index - 1
        while escape_index >= 0 and text[escape_index] == "\\":
            backslashes += 1
            escape_index -= 1
        if backslashes % 2 == 1:
            index += 1
            continue
        label_end = find_closing(text, bracket + 1, "[", "]")
        if label_end is None:
            index += 1
            continue
        label = text[bracket + 1:label_end]
        next_index = label_end + 1
        if next_index < len(text) and text[next_index] == "(":
            target_end = find_closing(text, next_index + 1, "(", ")")
            if target_end is not None:
                target = destination_from_parentheses(text[next_index + 1:target_end])
                if target is not None:
                    targets.append(target)
                index = target_end + 1
                continue
        if next_index < len(text) and text[next_index] == "[":
            reference_end = find_closing(text, next_index + 1, "[", "]")
            if reference_end is not None:
                reference = text[next_index + 1:reference_end] or label
                explicit_references.append(normalize_label(reference))
                index = reference_end + 1
                continue
        shortcut_references.append(normalize_label(label))
        index = label_end + 1

    for reference in explicit_references:
        if reference in definitions:
            targets.append(definitions[reference])
        else:
            targets.append(f"__MISSING_REFERENCE__:{reference}")
    for reference in shortcut_references:
        if reference in definitions:
            targets.append(definitions[reference])

    targets.extend(
        match.group(3)
        for match in re.finditer(r"\b(href|src)\s*=\s*([\"'])(.*?)\2", text, re.IGNORECASE)
    )
    return targets


def check_target(source: Path, raw_target: str):
    if raw_target.startswith("__MISSING_REFERENCE__:"):
        broken.append((source, raw_target.split(":", 1)[1], "missing reference definition"))
        return

    target = html.unescape(raw_target.strip())
    if not target or target.startswith("#") or target.startswith("//"):
        return
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
        return

    target = target.replace("\\ ", " ")
    parts = urlsplit(target)
    path_text = unquote(parts.path)
    if not path_text:
        return

    if path_text.startswith("/"):
        candidate = root / path_text.lstrip("/")
    else:
        candidate = source.parent / path_text
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        broken.append((source, raw_target, "target escapes repository"))
        return
    if not candidate.exists():
        broken.append((source, raw_target, "target not found"))


parser_sample = r'''
[nested](docs/example(1).md) [encoded](docs/example%20file.md?view=1#part)
![image](assets/example.png)
[reference][guide]
[guide]: docs/guide.md
<a href="docs/from-html.md#section">HTML</a>
`[inline-code](ignored.md)`
```markdown
[fenced-code](ignored.md)
```
'''
sample_targets = markdown_targets(strip_code(parser_sample))
expected_targets = {
    "docs/example(1).md",
    "docs/example%20file.md?view=1#part",
    "assets/example.png",
    "docs/guide.md",
    "docs/from-html.md#section",
}
if set(sample_targets) != expected_targets:
    print("  MARKDOWN PARSER ERROR: internal destination parsing self-check failed")
    raise SystemExit(1)


for current, directories, files in os.walk(root):
    directories[:] = [directory for directory in directories if directory not in excluded_dirs]
    current_path = Path(current)
    for filename in files:
        if not filename.lower().endswith(".md"):
            continue
        source = current_path / filename
        markdown = source.read_text(encoding="utf-8")
        markdown = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
        for target in markdown_targets(strip_code(markdown)):
            check_target(source, target)

if broken:
    for source, target, reason in broken:
        print(f"  BROKEN LINK: {source.relative_to(root)} -> {target} ({reason})")
    raise SystemExit(1)

print("  All internal Markdown links resolve.")
PY
then
    :
else
    FAILED=$((FAILED + 1))
fi
echo ""

# ---- Check 2: Committed Shell script modes ----
echo "--- Check 2: Committed Shell script modes ---"
MODE_ERRORS=0
CHECK_REV="HEAD"

if command -v jj >/dev/null 2>&1; then
    jj_revision=$(jj log -r @ --no-graph -T 'commit_id' 2>/dev/null || true)
    if [ -n "$jj_revision" ] && git cat-file -e "${jj_revision}^{commit}" 2>/dev/null; then
        CHECK_REV="$jj_revision"
    fi
fi

while IFS= read -r -d '' shell_file; do
    shell_file=${shell_file#./}
    mode=$(git ls-tree "$CHECK_REV" -- "$shell_file" 2>/dev/null | awk '{print $1}')
    if [ -z "$mode" ]; then
        echo "  NOT TRACKED: $shell_file (revision $CHECK_REV)"
        MODE_ERRORS=$((MODE_ERRORS + 1))
    elif [ "$mode" != "100755" ]; then
        echo "  NOT EXECUTABLE: $shell_file (mode $mode, expected 100755)"
        MODE_ERRORS=$((MODE_ERRORS + 1))
    fi
done < <(git ls-files -z -- '*.sh')

if [ "$MODE_ERRORS" -eq 0 ]; then
    echo "  All Shell scripts are committed as 100755."
else
    echo "  $MODE_ERRORS Shell script mode error(s)."
    FAILED=$((FAILED + 1))
fi
echo ""

# ---- Check 3: YAML syntax ----
echo "--- Check 3: YAML syntax ---"
YAML_ERRORS=0

if [ -z "$PYTHON" ] || ! "$PYTHON" -c "import yaml" 2>/dev/null; then
    echo "  UNAVAILABLE: Python with PyYAML is required."
    YAML_ERRORS=$((YAML_ERRORS + 1))
else
    while IFS= read -r -d '' yaml_file; do
        if ! "$PYTHON" -c 'import pathlib, sys, yaml; yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))' "$yaml_file" 2>/dev/null; then
            echo "  YAML ERROR: $yaml_file"
            YAML_ERRORS=$((YAML_ERRORS + 1))
        fi
    done < <(find . -type d \( -name '.git' -o -name '.jj' -o -name 'node_modules' -o -name '.venv' -o -name 'venv' -o -name '.cache' -o -name '__pycache__' \) -prune -o -type f \( -name '*.yml' -o -name '*.yaml' \) -print0)
fi

if [ "$YAML_ERRORS" -eq 0 ]; then
    echo "  All YAML files parse correctly."
else
    echo "  $YAML_ERRORS YAML validation error(s)."
    FAILED=$((FAILED + 1))
fi
echo ""

# ---- Check 4: Shell syntax ----
echo "--- Check 4: Shell syntax ---"
SHELL_ERRORS=0

while IFS= read -r -d '' shell_file; do
    if ! bash -n "$shell_file"; then
        echo "  SHELL SYNTAX ERROR: $shell_file"
        SHELL_ERRORS=$((SHELL_ERRORS + 1))
    fi
done < <(git ls-files -z -- '*.sh')

if [ "$SHELL_ERRORS" -eq 0 ]; then
    echo "  All Shell scripts pass syntax validation."
else
    echo "  $SHELL_ERRORS Shell syntax error(s)."
    FAILED=$((FAILED + 1))
fi
echo ""

echo "=== Results ==="
if [ "$FAILED" -eq 0 ]; then
    echo "All four technical checks passed."
else
    echo "$FAILED technical check(s) failed."
fi
exit "$FAILED"
