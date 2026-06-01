# Smoke B27.3 — Functional completion
$ErrorActionPreference = "Stop"
Write-Host "=== B27.3 Smoke ==="

. .venv\Scripts\Activate.ps1

# Architecture
python -m pytest tests/architecture/ -q
if ($LASTEXITCODE -ne 0) { throw "Architecture failed" }

# Create project with full data
python -m narrative_architect project create "B27_3_Full" --path b27_3_smoke.json
python -m narrative_architect entity create "Gandalf" --type personaje
python -m narrative_architect entity create "Mordor" --type faccion
python -m narrative_architect entity list --json

# Campaign
python -m narrative_architect campaign create "SombraCreciente" --system "D&D"
python -m narrative_architect campaign list --json

# Session with campaign
python -m narrative_architect session create "Sesion1" --campaign (python -c "import json; d=json.load(open('b27_3_smoke.json')); print(d['campaigns'][0]['id'])")

# Secrets + clues
python -m narrative_architect secret create "El anillo es peligroso"
python -m narrative_architect clue create "Gandalf sospecha" --secret (python -c "import json; d=json.load(open('b27_3_smoke.json')); print(d['secrets'][0]['id'])")

# Issues validation
python -m narrative_architect issue validate

# AI test
python -m narrative_architect ai generate-entity --prompt "fantasy wizard"

# Export no-leak
python -m narrative_architect export public-summary --json

Write-Host "Smoke B27.3 complete. Run: python -m hosts.DesktopHostPySide.main"
