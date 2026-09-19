# Dendro

Aplicación de escritorio para diseño narrativo y worldbuilding (PySide6, Python 3.12).
`README.md` manda sobre la estructura por capas de `packages/` y el flujo de desarrollo.

- El repositorio se llama `dendro` en GitHub desde hace poco; el nombre anterior,
  `narrative-architect`, sigue apareciendo en rutas y enlaces antiguos.
- El README documenta el entorno con rutas de Windows (`.venv/Scripts/python`). En este
  equipo, Linux, el equivalente es `.venv/bin/python`, y **este clon no trae `.venv`**:
  hay que crearlo antes de correr nada.
- Pruebas: `python -m pytest` (ver `scripts/run_all_tests.py`). Lint:
  `python -m ruff check packages/ tests/`. Escritorio:
  `python -m hosts.DesktopHostPySide.main`.
- Regla de producto que atraviesa el código: la IA sugiere y cultiva candidatos, pero
  **nunca modifica el canon** sin aceptación explícita del usuario.
- El capitán mantiene además un clon propio en `~/Projects/narrative-architect`, en la rama
  `beta-cierre`. Es una copia distinta de esta, no un enlace.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
