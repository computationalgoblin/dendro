# Local Desktop Readiness — B27.0

## Estado actual (2026-05-31)

El proyecto funciona dentro de Docker en `/workspace`. Para ejecución local:

| Item | Estado |
|------|--------|
| Python code | Sin hardcodes `/workspace` o `/tmp` |
| pyproject.toml | Configurado con entry point `narrative-architect` |
| pip install -e . | Funciona (packages find where=".") |
| Dependencias | pytest, ruff en `dev`; PySide6 en `desktop` |
| CLI | `python -m narrative_architect` o `narrative-architect` |
| DesktopHost | `python -m hosts.DesktopHostPySide.main` |
| Tests | 1117 passed, 9/9 arquitectura |
| AI Provider | DeepSeek/OpenAI con fallback simulado |

## Cómo ejecutar en Windows

```powershell
# Clonar repo
git clone <repo> narrative-architect
cd narrative-architect

# Setup
.\scripts\setup_local_windows.ps1

# CLI
python -m narrative_architect project create "Test" --path test.json
python -m narrative_architect entity create "Gandalf" --type personaje

# Desktop
python -m hosts.DesktopHostPySide.main

# Tests
python -m pytest tests/architecture/ -q
python -m pytest tests/domain/ tests/persistence/ tests/application/ -q
```

## Dependencias desktop

```bash
pip install narrative-architect[desktop]
# Instala: PySide6>=6.7.0
```

## Qué sigue

B27.1 — UI integral:
- Dashboard completo con tabs (corpus, campaign, sessions, candidates, export)
- Editor visual de entidades y relaciones
- Live mode visual
- Post-session review
- Graph view básico

## Qué queda fuera
- Instalador .exe final
- UI completa de writing
- Graph avanzado
- VTT
- Multiusuario
