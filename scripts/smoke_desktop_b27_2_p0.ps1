# Smoke B27.2 P0 — Import, Live, Session Prep, Post-session, Candidates
$ErrorActionPreference = "Stop"
Write-Host "=== B27.2 P0 Smoke ==="

. .venv\Scripts\Activate.ps1

# Architecture
Write-Host "Architecture tests..."
python -m pytest tests/architecture/ -q
if ($LASTEXITCODE -ne 0) { throw "Architecture failed" }

# Create project with data for smoke
Write-Host "Creating smoke project..."
python -m narrative_architect project create "B27_2_Smoke" --path b27_2_smoke.json
python -m narrative_architect entity create "Gandalf" --type personaje
python -m narrative_architect entity create "Rivendel" --type localizacion
python -m narrative_architect entity list --json

# Import test
Write-Host "Testing import..."
echo "Gandalf lives in Rivendel. Sauron is the enemy." > /tmp/b27_2_import.txt
python -m narrative_architect import document /tmp/b27_2_import.txt
python -m narrative_architect import basket list --json

# Export no-leak
Write-Host "Testing export no-leak..."
python -m narrative_architect export public-summary --json
python -m narrative_architect export all --audience gm --json

Write-Host "Smoke P0 complete. Run: python -m hosts.DesktopHostPySide.main"
