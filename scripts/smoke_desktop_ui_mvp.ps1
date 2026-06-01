# Smoke Desktop UI MVP — B27.1-T06
$ErrorActionPreference = "Stop"

Write-Host "=== Desktop UI MVP Smoke ==="

# Activate venv if exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    . .venv\Scripts\Activate.ps1
    Write-Host "venv activated"
}

# Architecture tests
Write-Host "Running architecture tests..."
python -m pytest tests/architecture/ -q
if ($LASTEXITCODE -ne 0) { Write-Host "ARCHITECTURE FAILED"; exit 1 }

# Create smoke project
Write-Host "Creating smoke project..."
python -m narrative_architect project create "DesktopSmoke" --path desktop_smoke.json
python -m narrative_architect entity create "Gandalf" --type personaje
python -m narrative_architect entity create "Rivendel" --type localizacion
python -m narrative_architect entity list --json

# Import controllers (no display needed)
Write-Host "Importing DesktopHost controllers..."
python -c "from hosts.DesktopHostPySide.controllers.project_controller import ProjectController; print('ProjectController OK')"
python -c "from hosts.DesktopHostPySide.controllers.entity_controller import EntityController; print('EntityController OK')"
python -c "from hosts.DesktopHostPySide.app_context import AppContext; print('AppContext OK')"

Write-Host "Smoke complete. Run: python -m hosts.DesktopHostPySide.main"
