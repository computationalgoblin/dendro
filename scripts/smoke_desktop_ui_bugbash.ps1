param(
    [string]$TargetRoot = $(Join-Path (Split-Path -Parent $PSScriptRoot) 'local_ui_bugbash')
)

& (Join-Path $PSScriptRoot 'smoke_desktop_b27_3.ps1') -TargetRoot $TargetRoot
exit $LASTEXITCODE
