param(
    [switch]$Fast,
    [string]$Suites = "arch sanity b39"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ([string]::IsNullOrWhiteSpace($Suites)) {
    throw "-Suites cannot be empty"
}

Write-Host "[verify_all] root: $Root"
Write-Host "[verify_all] compileall"
python -m compileall hosts/DesktopHostPySide packages tests -q

Write-Host "[verify_all] architecture"
python -m pytest tests/architecture/ -q

Write-Host "[verify_all] suites: $Suites"
$parts = $Suites -split '\s+'
python scripts/run_all_tests.py --suites @parts

Write-Host "[verify_all] PASS"
