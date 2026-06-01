# Local Desktop Setup — Windows

$ErrorActionPreference = "Stop"

# 1. Create virtual environment
py -3.12 -m venv .venv
. .venv\Scripts\Activate.ps1

# 2. Update pip
python -m pip install --upgrade pip

# 3. Install project in editable mode with dev deps
python -m pip install -e ".[dev]"

# 4. Install desktop dependencies (PySide6)
python -m pip install -e ".[desktop]"

# 5. Smoke test — package imports
python -c "from packages.application.project_service import ProjectService; print('ProjectService OK')"
python -c "from hosts.DesktopHostPySide.main_window import MainWindow; print('MainWindow OK')"

# 6. Run architecture tests (MUST pass)
Write-Host "Running architecture tests..."
python -m pytest tests/architecture/ -q
if ($LASTEXITCODE -ne 0) { Write-Host "ARCHITECTURE FAILED — aborting setup"; exit 1 }

# 7. Verify no persistence/infrastructure imports in DesktopHost
$vio = Select-String -Path hosts/DesktopHostPySide/*.py,hosts/DesktopHostPySide/**/*.py -Pattern "packages.persistence|packages.infrastructure" | Select-Object -First 5
if ($vio) { Write-Host "ARCHITECTURE VIOLATION: DesktopHost imports persistence/infrastructure"; $vio; exit 1 }

Write-Host "Setup complete. Run: python -m hosts.DesktopHostPySide.main"
