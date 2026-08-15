# Untitled self-management entry point.
# ASCII-only output (GBK-safe), PowerShell 5.1 compatible. Run: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/manage.ps1 <command>
#
# Commands:
#   status        Git state (branch, remote, dirty files) + tool readiness summary
#   validate      Run the authoritative validation entry (scripts/validate.ps1)
#   check-tools   Show download tool readiness via untitled.py check-tools
#   projects      List output/ projects (real vs test leftovers)
#   disk          Show repository disk usage summary
#   help          Show this help

param(
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $RepoDir

function Write-Note {
    Write-Host "[manage] $args" -ForegroundColor Cyan
}

function Show-Help {
    Write-Host "Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/manage.ps1 <command>"
    Write-Host "Commands: status | validate | check-tools | projects | disk | help"
}

function Show-Status {
    Write-Note "git branch:"
    git branch --show-current
    Write-Host ""
    Write-Note "git status:"
    git status --short --branch
    Write-Host ""
    Write-Note "remotes:"
    git remote -v
    Write-Host ""
    Write-Note "tool readiness (untitled.py check-tools):"
    python untitled.py check-tools 2>&1 | Select-String -Pattern '"status"|"ready"|"required"|"error"' | Select-Object -First 20
}

function Invoke-Validate {
    Write-Note "Running authoritative validation: scripts/validate.ps1"
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validate.ps1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[manage] VALIDATION FAILED (exit $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "[manage] VALIDATION PASSED" -ForegroundColor Green
}

function Show-Tools {
    python untitled.py check-tools
    exit $LASTEXITCODE
}

function Show-Projects {
    if (-not (Test-Path "output")) {
        Write-Note "No output/ directory yet."
        return
    }
    $dirs = Get-ChildItem "output" -Directory -Force
    $leftover = @()
    $other = @()
    foreach ($d in $dirs) {
        # Only names with explicit test markers (tmp / -test / test-) are classified
        # as leftovers; everything else is listed for human confirmation.
        if ($d.Name -match "(tmp|test)") {
            $leftover += $d.Name
        } else {
            $other += $d.Name
        }
    }
    Write-Note "Test leftovers (gitignored, safe to remove): $($leftover.Count)"
    $leftover | Select-Object -First 15 | ForEach-Object { Write-Host "  $_" }
    if ($leftover.Count -gt 15) { Write-Host "  ... and $($leftover.Count - 15) more" }
    Write-Host ""
    Write-Note "Other output/ entries (no test marker, confirm before touching): $($other.Count)"
    if ($other.Count -eq 0) { Write-Host "  (none)" }
    $other | ForEach-Object { Write-Host "  $_" }
}

function Show-Disk {
    $targets = @("output", "migration-backups", "download-tools", ".venv")
    foreach ($t in $targets) {
        if (Test-Path $t) {
            $sum = (Get-ChildItem $t -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
            $mb = [math]::Round($sum / 1MB, 1)
            Write-Host ("{0,-20} {1,10} MB" -f $t, $mb)
        }
    }
    $total = (Get-ChildItem . -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    Write-Host ("{0,-20} {1,10} MB" -f "TOTAL", [math]::Round($total / 1MB, 1))
}

switch ($Command.ToLower()) {
    "status"       { Show-Status }
    "validate"     { Invoke-Validate }
    "check-tools"  { Show-Tools }
    "projects"     { Show-Projects }
    "disk"         { Show-Disk }
    "help"         { Show-Help }
    default        { Show-Help }
}
