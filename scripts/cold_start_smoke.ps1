[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$RepositoryRoot = "",

    [Parameter(Mandatory = $false)]
    [string]$ReportPath = "",

    [switch]$AllowExistingTools
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# $PSScriptRoot is not available inside parameter default-value expressions
# (parameter binding runs before the script body), so resolve the default
# repository root here.
if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$root = (Resolve-Path $RepositoryRoot).Path
$toolsRoot = Join-Path $root "download-tools"
$fetchScript = Join-Path $root "scripts\fetch_tools.py"
$cli = Join-Path $root "untitled.py"

if (-not (Test-Path $fetchScript -PathType Leaf)) {
    throw "fetch_tools.py not found: $fetchScript"
}
if (-not (Test-Path $cli -PathType Leaf)) {
    throw "untitled.py not found: $cli"
}

$installedFiles = Get-ChildItem $toolsRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notin @("README.md", "tools.json", "routing.json", "THIRD_PARTY_NOTICES.md") }
if ($installedFiles -and -not $AllowExistingTools) {
    throw "download-tools already contains installed files. Run in a fresh clone or pass -AllowExistingTools."
}

$started = Get-Date
$steps = New-Object System.Collections.Generic.List[object]

function Invoke-CheckedStep {
    param(
        [string]$Name,
        [string[]]$Command
    )
    $stepStarted = Get-Date
    $executable = $Command[0]
    $arguments = @()
    if ($Command.Length -gt 1) {
        $arguments = $Command[1..($Command.Length - 1)]
    }
    $output = & $executable @arguments 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    $steps.Add([pscustomobject]@{
        name = $Name
        command = ($Command -join " ")
        exit_code = $exitCode
        output = $output.Trim()
        duration_seconds = [math]::Round(((Get-Date) - $stepStarted).TotalSeconds, 3)
    })
    if ($exitCode -ne 0) {
        throw "$Name failed with exit code $exitCode`n$output"
    }
}

Push-Location $root
try {
    Invoke-CheckedStep "verify-manifest" @("python", "scripts/fetch_tools.py", "--verify-manifest")
    Invoke-CheckedStep "fetch-tools" @("python", "scripts/fetch_tools.py")
    Invoke-CheckedStep "cli-check-tools" @("python", "untitled.py", "check-tools")
    Invoke-CheckedStep "cli-help" @("python", "untitled.py", "--help")
    Invoke-CheckedStep "validate-powershell" @(
        "powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/validate.ps1"
    )
}
finally {
    Pop-Location
}

$report = [pscustomobject]@{
    schema_version = 1
    repository_root = $root
    platform = [System.Environment]::OSVersion.VersionString
    powershell = $PSVersionTable.PSVersion.ToString()
    started_at = $started.ToUniversalTime().ToString("o")
    completed_at = (Get-Date).ToUniversalTime().ToString("o")
    status = "PASS"
    steps = $steps
}

if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $ReportPath = Join-Path $root "migration-backups\cold-start-smoke-report.json"
    $reportDirectory = Split-Path -Parent $ReportPath
    New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
}
$report | ConvertTo-Json -Depth 8 | Set-Content -Path $ReportPath -Encoding utf8
Write-Host "Cold-start smoke passed. Report: $ReportPath"
