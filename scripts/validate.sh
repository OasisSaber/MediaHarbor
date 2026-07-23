#!/bin/bash
set -o pipefail

FAILED=0
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR" || exit 1

echo "=== MediaHarbor Validation ==="
echo ""

# ---- Check 1: Ruff format ----
echo "--- Check 1: Ruff format ---"
if python -m ruff format --check . 2>&1; then
    echo "  Format check passed."
else
    echo "  Format check failed."
    FAILED=$((FAILED + 1))
fi
echo ""

# ---- Check 2: Ruff lint ----
echo "--- Check 2: Ruff lint ---"
if python -m ruff check . 2>&1; then
    echo "  Lint check passed."
else
    echo "  Lint check failed."
    FAILED=$((FAILED + 1))
fi
echo ""

# ---- Check 3: Pytest ----
echo "--- Check 3: Pytest ---"
if python -m pytest -v 2>&1; then
    echo "  All tests passed."
else
    echo "  Tests failed."
    FAILED=$((FAILED + 1))
fi
echo ""

# ---- Check 4: locate_root smoke test ----
echo "--- Check 4: locate_root.py smoke test ---"
if python skill/mediaharbor/scripts/locate_root.py --json 2>&1; then
    echo "  locate_root.py OK."
else
    echo "  locate_root.py failed."
    FAILED=$((FAILED + 1))
fi
echo ""

# ---- Check 5: check_tools smoke test ----
echo "--- Check 5: check_tools.py smoke test ---"
if python skill/mediaharbor/scripts/check_tools.py --json 2>&1; then
    echo "  check_tools.py OK."
else
    echo "  check_tools.py failed."
    FAILED=$((FAILED + 1))
fi
echo ""

echo "=== Results ==="
if [ "$FAILED" -eq 0 ]; then
    echo "All checks passed."
else
    echo "$FAILED check(s) failed."
fi
exit "$FAILED"
