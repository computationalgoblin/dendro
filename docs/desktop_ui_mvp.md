# Desktop UI MVP — Narrative Architect

## Cómo ejecutar

```powershell
# Windows
.\scripts\setup_local_windows.ps1
python -m hosts.DesktopHostPySide.main

# Linux/macOS
pip install -e ".[desktop]"
python -m hosts.DesktopHostPySide.main
```

## Pantallas implementadas

| Sección | Stack index | Funcionalidad |
|---------|-------------|---------------|
| Dashboard | 0 | Counts reales (entities, relations, candidates, sessions, campaigns, secrets, factions, clocks, fronts), open/create/save |
| Corpus | 1 | Tabla de entidades con filtros (texto, tipo, canon), crear entidad (diálogo), editar (name, description), detalle |
| Relations | 2 | Tabla source→type→target, crear relación (selectores source/target/type) |
| Candidates | 3 | Tabla de candidates con type/state/source, detalle (proposed_data, metadata, source_id), accept/reject |
| Issues/History | 4 | Issues abiertas (type, severity, description) + History entries recientes (timestamp, event, description) |
| Sessions | 5 | Tabla de sesiones (name, state, campaign), crear sesión |
| Live/Post | 6 | Live tab: open, note, entity, clue, secret, improvise, done. Post tab: close, candidates, accept, reject, source, seeds |
| Import/Export | 7 | Import: selector archivo, baskets. Export: audience gm/player/public, export all/entity/session con selectores locales |

## Acciones pendientes / TODO

- Live: diálogos de texto para note/decide/event/consequence (botones con TODO)
- Live: selector de clue/secret en deliver/reveal
- Import: integración completa con ImportService (basket detail, accept/reject)
- Export: integración completa con ExportService (player/public sin leak)
- Candidate: integration with CandidateService for accept/reject (currently delegates to project)
- Grafos y vistas avanzadas (B28)

## Límites conocidos

- La UI no reemplaza aún todos los comandos CLI. La CLI sigue siendo necesaria para operaciones avanzadas
- Import/export requiere CLI para flujos completos (basket review)
- Live/Post tiene acciones con TODO; funcional pero con UX mínima
- Sin tests de UI automatizados (solo smoke manual)

## Arquitectura MVC

```
hosts/DesktopHostPySide/
  main.py                    ← entry point
  main_window.py             ← shell: sidebar + stack + topbar
  app_context.py             ← shared state (project, selections, audience, log)
  controllers/
    project_controller.py    ← ProjectService wrapper
    entity_controller.py     ← EntityService wrapper
    relation_controller.py   ← RelationService wrapper
    candidate_controller.py  ← CandidateService wrapper
    session_controller.py    ← Session/Live/Post services
  views/
    dashboard_view.py
    corpus_view.py
    relation_view.py
    candidate_view.py
    issues_history_view.py
    session_view.py
    live_post_view.py
    import_export_view.py
```

Reglas: UI solo importa packages.application y packages.domain. Nunca persistence/infrastructure.
