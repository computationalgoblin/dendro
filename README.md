# Dendro (narrative-architect)

**Dendro** es una aplicación de escritorio para creación narrativa, worldbuilding
y escritura asistida por IA.

El núcleo conceptual es una **base de conocimiento narrativa estructurada**:
no un chatbot, no una wiki pasiva, no un VTT y no un grafo decorativo.
La IA asiste, sugiere y cultiva candidatos ("semillas"), pero **nunca modifica el
canon** sin aceptación explícita del usuario.

> **¿Usuario final?** Lee [README-USUARIO.md](README-USUARIO.md): descargar,
> ejecutar `Dendro.exe`, configurar tu proveedor de IA y crear tu primer proyecto.
> Estado: **beta** (0.9.0b1). El resto de este documento es para desarrollo.

## Desarrollo

```bash
# Entorno: virtualenv del repo (deps ya instaladas)
.venv/Scripts/python -m pytest                       # pruebas (ver scripts/run_all_tests.py)
.venv/Scripts/python -m ruff check packages/ tests/  # lint

# CLI
python -m narrative_architect <comando> [--project RUTA]

# Escritorio (PySide6, extra `desktop`)
python -m hosts.DesktopHostPySide.main

# Build del ejecutable Windows (PyInstaller, extra `dev`)
python scripts/build_desktop.py     # → dist/Dendro/Dendro.exe
```

## Estructura del repositorio

```
packages/
├── domain/                — Modelo de dominio puro (stdlib, sin dependencias)
├── application/           — Casos de uso, servicios, orquestación de IA
├── infrastructure/        — Adaptadores de proveedores de IA
├── persistence/           — ProjectStore + migraciones de esquema versionadas
└── ui/                    — Host CLI
hosts/DesktopHostPySide/   — Host de escritorio (PySide6)
packaging/                 — Spec de PyInstaller
docs/contracts/            — Contratos autoritativos (mandan sobre sugerencias)
tests/                     — Pruebas por capa (runner: scripts/run_all_tests.py)
```

## Arquitectura limpia

```
ui → application → domain
infrastructure → application/domain
persistence → domain
```

El dominio **no depende** de UI, IA, frameworks visuales ni proveedores externos.
Las reglas de dependencia se verifican estáticamente en `tests/architecture/`.

## Principios

1. **El core manda** — el modelo de dominio es la fuente de verdad.
2. **El grafo no es la base de datos** — es una vista interactiva.
3. **La IA no modifica canon** — produce candidatos revisables, no muta.
4. **Todo cambio relevante es trazable** — origen, estado, historial.
5. **Secretos y visibilidad se respetan siempre** — no filtrar información no autorizada.
6. **No modelos paralelos** — si el core lo representa, reutilizar.
7. **La UI no escribe en persistencia** — siempre a través de servicios.
8. **La aplicación funciona sin IA** — la IA es asistencia opcional.
9. **Contratos prevalecen** — sobre sugerencias creativas de agentes.
