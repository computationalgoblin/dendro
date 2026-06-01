# Local Desktop Setup — Windows

# 1. Create virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Update pip
python -m pip install --upgrade pip

# 3. Install project in editable mode
python -m pip install -e .

# 4. Install desktop dependencies (PySide6)
python -m pip install -e ".[desktop]"

# 5. Smoke test
python -c "from packages.application.project_service import ProjectService; print('OK')"
python -m narrative_architect --help
python -m pytest tests/architecture/ -q

Write-Host "Setup complete. Run: python -m hosts.DesktopHostPySide.main"
