# Desktop UI Bug Bash B27.3

## Resumen
- Fecha: 2026-06-01T12:30:18+00:00
- Rama/commit: master @ 0258537ab10fb313f34abff6c92bf68c5b253c9b (working tree con cambios locales)
- Windows validado: no
- Python version: 3.12.3
- Tests architecture: 9/9 passing
- Total casos: 18
- P0 abiertos: 0
- P1 abiertos: 7
- Casos verdes: 4

Notas de lectura:
- "corregido" = fix aplicado en código + compileall/pytest verdes, pero todavía sin smoke manual del usuario en Windows.
- "verificado" = hay evidencia ejecutada en este entorno (tests, smoke CLI, compileall).
- B27.3 NO está cerrada todavía porque falta validación manual real de Desktop UI en Windows.

## Matriz de casos

| ID | Pantalla | Función | CLI equivalente | Servicio | Prioridad | Estado | Pasos | Esperado | Real | Log/Traceback | Fix commit |
|----|----------|---------|----------------|----------|-----------|--------|-------|----------|------|---------------|------------|
| B27.3-P0-01 | Arranque | Importar módulos DesktopHostPySide | n/a | n/a | P0 | verificado | `python -m compileall hosts/DesktopHostPySide` | Sin NameError/IndentationError/SyntaxError | Compileall OK tras rehacer main_window/controllers/views clave | Sin traceback en compileall; smoke visual Windows pendiente | working tree |
| B27.3-P0-02 | Corpus | Doble click abre ficha completa de entidad | `entity show` | EntityService + RelationService | P0 | corregido | Abrir Corpus, seleccionar entidad, doble click | Ficha con id completo, canon, visibility, descripción, metadata y relaciones vinculadas | View reescrita para usar ID real vía Qt.UserRole + detalle ampliado | Pendiente smoke Windows/PySide real | working tree |
| B27.3-P0-03 | Relations | Doble click abre ficha completa de relación | `relation show` | RelationService | P0 | corregido | Abrir Relations, seleccionar relación, doble click | Ficha con source/target, type, metadata, canon | View reescrita; conexión doubleClicked + QTextEdit + ID real | Pendiente smoke Windows/PySide real | working tree |
| B27.3-P0-04 | Import | Import txt usa format correcto | `import document --format txt` | ImportService | P0 | corregido | Seleccionar `.txt` desde UI | `ImportService.import_document()` recibe txt correcto, crea basket | Controller ya infiere `.txt/.pdf`; view reescrita para aceptar/rechazar con IDs completos | Smoke UI pendiente; smoke CLI del import OK | working tree |
| B27.3-P0-05 | AI | UI usa provider real / error real | `ai ...` | OrchestratorService | P0 | corregido | Ver topbar + botón Test AI | Provider real visible; nunca fallback silencioso si hay env vars; error real al fallar | Añadido AIController; topbar usa env real y `Test AI` loguea error real | Falta validación manual con OpenCode Zen en Windows | working tree |
| B27.3-P0-06 | Campaign | Crear/mostrar campaña real | `campaign create/show/overview` | CampaignService | P0 | corregido | Crear campaña, añadir player, crear clock, ver overview | Alta/overview reales contra servicio | Controller/view reescritos; smoke CLI campaña/player/clock OK | UI Windows pendiente | working tree |
| B27.3-P0-07 | Factions | Crear extensión Faction desde entidad FACCIÓN | `faction create` | FactionService | P0 | corregido | Crear entidad facción, luego extensión desde vista | Entidad pendiente visible y extensión gestionable | Nuevo FactionController + pending_faction_entities; smoke CLI faction OK | UI Windows pendiente | working tree |
| B27.3-P0-08 | Issues | Validadores visibles y ejecutables desde UI | `issue ...`, `secret detect-issues`, `faction ...`, `session check` | IssueService + SecretsService + FactionService + WritingService + SessionService | P0 | corregido | Ejecutar validación global/especializada | Issues visibles y sin traceback | Nueva vista/controller de issues con validadores global/writing/secret/faction/session | Pendiente validar deduplicación visual/manual | working tree |
| B27.3-P0-09 | CLI base | `secret`/`clue` registrados en parser root | `secret --help`, `clue --help` | CLI dispatch | P0 | verificado | Ejecutar `python -m narrative_architect secret --help` y `clue --help` | Comandos disponibles | Antes faltaba `register_secrets_commands`; ahora ambos ayudan correctamente | Sin traceback | working tree |
| B27.3-P0-10 | Smoke setup | Dataset mínimo reproducible para UI | múltiples | múltiples | P0 | corregido | Ejecutar `scripts/smoke_desktop_b27_3.ps1` | Si falla cualquier paso, aborta con exit 1; si pasa, deja JSON válido + `latest_project_path.txt` | Script rehecho para ruta absoluta Windows, path timestamped, `--project` global, captura robusta de IDs, y sin falsos positivos de "complete" | Aún no validado ejecutándolo en Windows real | working tree |
| B27.3-P1-01 | Project | Topbar counts / refresh global | `project open/save` | ProjectService | P1 | corregido | Abrir/guardar y navegar vistas | Counts coherentes tras refresh | MainWindow ahora refresca stack y log sink compartido | Falta validación manual Windows | working tree |
| B27.3-P1-02 | Candidates | Accept/Reject/merge sin usar IDs truncados | `candidate accept/reject/merge` | CandidateService | P1 | corregido | Seleccionar candidate desde vista y actuar | Cambio de estado real sin duplicados | Controller estable; revisión manual UI aún pendiente | Smoke visual pendiente | working tree |
| B27.3-P1-03 | Sessions | Crear sesión + escena + checks básicos | `session create/scene/check/suggest` | SessionService | P1 | corregido | Crear sesión vinculada a campaña y añadir escena | Alta y escenas reales; check/suggest visibles | SessionView reescrita; smoke CLI session create + scene add OK | Faltan pruebas manuales de reorder/link UX | working tree |
| B27.3-P1-04 | Live | Notas, decisiones, eventos, secreto/pista | `session live ...` | LiveModeService | P1 | corregido | Abrir Live y disparar acciones | metadata[`live`] y acciones reales | LivePostView reescrita contra controller; smoke visual pendiente | Falta validación manual Windows | working tree |
| B27.3-P1-05 | Post-session | Cerrar sesión, resumir, generar candidates | `session close/post-*` | PostSessionService | P1 | corregido | Ejecutar acciones post | Resúmenes/candidates/source/seeds reales | LivePostView usa PostSessionController real | Idempotencia visual/manual pendiente | working tree |
| B27.3-P1-06 | Export | export entity/session/campaign + all | `export ...` | ExportService | P1 | corregido | Export desde vista | Texto exportado según audiencia | ImportExportView reescrita con export all + single | Falta smoke manual no-leak en Windows | working tree |
| B27.3-P1-07 | Writing | writing básico desde UI | `writing create/show/...` | WritingService | P1 | abierto | Abrir Writing y probar árbol/edición | Crear/abrir/editar unidad y links básicos | No auditado ni smokeado todavía en esta ronda | Pendiente | — |
| B27.3-P1-08 | Timeline/Framework/Sources/Layers | Cobertura real vs sólo pantalla | `timeline/framework/source/layer ...` | varios | P1 | diferido | Abrir cada pantalla y verificar acciones reales | Debe quedar explícito si existe o no | Auditoría automática creada, pero falta smoke funcional de cada módulo | Pendiente | — |

Pruebas ejecutadas en esta ronda:
- `python -m compileall hosts/DesktopHostPySide` → OK
- `python -m pytest tests/architecture/ -q` → 9 passed
- `python -m pytest tests/domain/ tests/persistence/ tests/application/ -q` → 1108 passed
- Smoke CLI manual del dataset B27.3 en Linux: `/workspace/tmp/desktop_ui_bugbash/desktop_ui_bugbash_project.json` → OK
- Script Windows real: `scripts/smoke_desktop_b27_3.ps1`
  - target root default: `C:\dev\narrative-architect\local_ui_bugbash`
  - proyecto final: `desktop_ui_bugbash_project_<timestamp>.json`
  - puntero al proyecto listo para abrir: `latest_project_path.txt`
  - log: `desktop_ui_bugbash_setup.log`
  - el script aborta en el primer error y NO imprime OK/complete si hay fallos

Observación importante sobre validación Windows:
- No afirmo validación Windows porque aquí no hay PowerShell disponible.
- Sí validé el equivalente CLI en Linux y corregí además un bug real de dispatch en `packages/ui/cli.py` para `export`.

Bloqueantes restantes para cerrar B27.3:
1. Validación manual/visual real de Windows.
2. Confirmar que el runtime Desktop carga PySide6 y arranca sin traceback en el entorno del usuario.
3. Pasar checklist manual completa de `docs/desktop_ui_manual_test_B27_3.md`.
4. Revisar módulos P1/P2 todavía no smokeados (Writing, Timeline, Framework, Sources, Layers).
