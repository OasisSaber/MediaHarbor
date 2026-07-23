$ErrorActionPreference = "Continue"
$Failed = 0
$RepoDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $RepoDir

Write-Host "=== MediaHarbor Validation ===" -ForegroundColor Cyan
Write-Host ""

# Check 1: Ruff format
Write-Host "--- Check 1: Ruff format ---" -ForegroundColor Yellow
python -m ruff format --check .
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Format check failed." -ForegroundColor Red
    $Failed++
} else {
    Write-Host "  Format check passed." -ForegroundColor Green
}
Write-Host ""

# Check 2: Ruff lint
Write-Host "--- Check 2: Ruff lint ---" -ForegroundColor Yellow
python -m ruff check .
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Lint check failed." -ForegroundColor Red
    $Failed++
} else {
    Write-Host "  Lint check passed." -ForegroundColor Green
}
Write-Host ""

# Check 3: Pytest
Write-Host "--- Check 3: Pytest ---" -ForegroundColor Yellow
python -m pytest -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Tests failed." -ForegroundColor Red
    $Failed++
} else {
    Write-Host "  All tests passed." -ForegroundColor Green
}
Write-Host ""

# Check 4: locate_root smoke test
Write-Host "--- Check 4: locate_root.py smoke test ---" -ForegroundColor Yellow
python skill/mediaharbor/scripts/locate_root.py --json
if ($LASTEXITCODE -ne 0) {
    Write-Host "  locate_root.py failed." -ForegroundColor Red
    $Failed++
} else {
    Write-Host "  locate_root.py OK." -ForegroundColor Green
}
Write-Host ""

# Check 5: check_tools smoke test
Write-Host "--- Check 5: check_tools.py smoke test ---" -ForegroundColor Yellow
python skill/mediaharbor/scripts/check_tools.py --json
if ($LASTEXITCODE -ne 0) {
    Write-Host "  check_tools.py failed." -ForegroundColor Red
    $Failed++
} else {
    Write-Host "  check_tools.py OK." -ForegroundColor Green
}
Write-Host ""

Write-Host "=== Results ===" -ForegroundColor Cyan
if ($Failed -eq 0) {
    Write-Host "All checks passed." -ForegroundColor Green
} else {
    Write-Host "$Failed check(s) failed." -ForegroundColor Red
}
exit $Failed
