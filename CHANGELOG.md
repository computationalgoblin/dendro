# CHANGELOG — Dendro / Narrative Architect

Formato basado en bloques. Este archivo resume cambios relevantes para humanos; no sustituye a `git log`, Kanban ni cierres técnicos.

## 2026-06-07 — Repaso UI/UX de armonía, movimiento y feedback

### Mejorado

- Diseño global: estados `hover`, `focus`, `pressed` y `disabled` más consistentes para botones, campos y toolbuttons.
- Movimiento: helper `fade_in()` y `pulse_feedback()` en `design_system.py`; drawers izquierdo/derecho animan suavemente el contenido al abrir/cambiar panel.
- Feedback inmediato: status bar ambiental en `MainWindow`, conectado a `log_msg()` para mostrar navegación, errores y acciones sin abrir el log técnico.
- Creación/grafo: command bar IA más clara, menos técnica y con feedback visual para job creado, progreso, éxito y error.
- Cámara: zoom de grafo más suave y acotado para evitar zoom infinito/accidental.
- Lenguaje visible: `Jobs` → `Tareas`, `Fit all` → `Encajar`, `Reset` → `Centrar`, `Global` → `Mostrando todo`.
- Descubribilidad: tooltips en tarjetas Home y Dendro command bar.

### Verificación

- `python -m py_compile` sobre módulos UI afectados: OK.
- Windows visual pendiente de validación manual.

## 2026-06-07 — Validación visual Windows B30-B43 + diagnóstico de bugs

### Ejecutado

- Validación visual interactiva con script `scripts/validate_visual_B30_B43.py`.
- 95 checks ejecutados: 41 PASA, 11 FALLA, 43 N/A.
- B30-B33 y B39-B40 PASAN en Windows nativo.

### Bugs confirmados (10)

- BUG-B34-PANEL: panel detalle rama no aparece (event propagation).
- BUG-B34-BADGE: badge miembros flota al colapsar.
- BUG-B34-RELINT: no se puede relacionar nodo interno con rama.
- BUG-B34-CYCLE: prevención de ciclos sólo visual, sin enforcement.
- BUG-B35-REPAIR: reparación coherencia no editable, no persiste, se pierde al cerrar drawer.
- BUG-B36-WB: toggle worldbuilding no propaga al canvas (asimetría activate/deactivate).
- BUG-B36-TYPO: `worldbuilding_enabled` vs `worldbuilding_active` en tree_detail_panel.py.
- BUG-B37-FOCUS: focus vecindad filtra ancestros contenedores.
- BUG-B37-CAM: no hay zoom/pan interactivo con ratón (falta feature).
- BUG-B38-ERROR: error provider poco prominente en UI (gap testabilidad).

### Documentación actualizada

- `KNOWN_ISSUES.md`: 10 bugs nuevos con causa raíz y criterio de cierre.
- `docs/agents/HANDOFF.md`: estado actualizado con resultados validación.
- `PHASE_CURRENT.md`: fase redefinida con bugs confirmados.
- `scripts/validate_visual_B30_B43.py`: script interactivo de validación.

## 2026-06-06 — Sincronización documental post-B43

### Corregido

- `HANDOFF`, `ROADMAP`, `PHASE_CURRENT` y `KNOWN_ISSUES` dejan de apuntar a fases antiguas como estado activo.
- Se registra explícitamente que el último bloque implementado es B43 y que no hay B44 autorizado.
- Se amplía la deuda Windows pendiente a B36-B43.
- Se registra deuda documental por cierres dedicados ausentes en B37/B38/B41/B42/B43.

### Cierres documentales añadidos

- `docs/cierres/bloque-37-cierre.md`
- `docs/cierres/bloque-38-cierre.md`
- `docs/cierres/bloque-39-cierre.md`
- `docs/cierres/bloque-41-cierre.md`
- `docs/cierres/bloque-42-cierre.md`
- `docs/cierres/bloque-43-cierre.md`
- `docs/cierres/bloque-40-configuracion-creativa.md` queda marcado como aprobado/cerrado documentalmente, manteniendo Windows pendiente.
- `docs/pruebas/prueba_visual_guiada_B30_B43.md` añade una prueba visual guiada integral para validar en Windows todos los elementos implementados desde B30.

### Validación

- Revisión documental y de estructura con herramientas (`git status`, `git log`, `scripts/run_all_tests.py`, `packages/persistence/schema.py`, búsqueda de docs/tests).
- No se ejecutó `python scripts/run_all_tests.py` en esta pasada.

## 2026-06-06 — B43 Prompt Registry migration

### Añadido/Cambiado

- Migración completa de prompts IA inline al Prompt Registry para command bar, IA inline de hoja/rama/relación y coherencia/reparación.
- Static guard para impedir nuevos prompts inline largos fuera de `prompt_registry.py`.
- Suite `b43` registrada en `scripts/run_all_tests.py`.

### Estado

- Implementado en WSL/offscreen según evidencia local.
- Validación Windows nativa pendiente.

## 2026-06-06 — B42 Hardening y eficiencia de IA

### Añadido

- `AIRequestGateway` como pipeline central: construir contexto, sanitizar, aplicar parámetros, invocar provider y validar salida.
- Context sanitizer recursivo.
- Model params policy por intención.
- Prompt Registry inicial.
- Output Schema Validator.
- Coherencia estructurada.
- Observability ring buffer sin exponer API keys.
- Deduplicación de candidatos.
- Marcadores legacy en rutas antiguas.

### Estado

- Implementado en WSL/offscreen según evidencia local.
- Validación Windows nativa pendiente para flujos afectados.

## 2026-06-06 — B41 Milestones causales

### Añadido

- Modelo `CausalMilestone` y persistencia schema v23.
- `CausalMilestoneService` con CRUD y construcción de grafo.
- Panel Desktop y botón de toolbar.
- Creación de hito desde selección del grafo.
- Clasificación IA para milestones.
- Reviewer de candidatos de milestone.
- Status quo explainer basado en milestones.

### Estado

- Implementado en WSL/offscreen según evidencia local.
- Validación Windows nativa pendiente.

## 2026-06-05 — B40 Configuración creativa + Wizard

### Añadido

- `CreativeProjectConfig` expandido con intención creativa, motor narrativo, poética, canon, espacio negativo y memoria de gusto.
- `AIConfig` expandido.
- 10 presets creativos.
- Configuración por rama con herencia Proyecto → Anillo → Rama padre → Rama/Hoja.
- Panel de configuración creativa con 9 pestañas.
- Wizard inicial de 8 pasos.
- Contexto IA enriquecido con perfil creativo.

### Corregido

- Guardado del wizard en el JSON seleccionado.
- Los candidatos IA pendientes no se renderizan como entidades del grafo.
- Panel de configuración abre correctamente tras el refactor a pestañas.

### Estado

- Implementado en WSL/offscreen.
- Validación Windows nativa pendiente.
- Cierre: `docs/cierres/bloque-40-configuracion-creativa.md`.

## 2026-06-05 — B39 Modelo visible + control operativo

### Añadido/Cambiado

- Modelo visible Hoja/Rama/Anillo en UX/docs/prompts IA, sin renombrar clases internas.
- Transformaciones hoja→rama y rama→anillo.
- Artefactos de control operativo:
  - `ROADMAP.md`
  - `PHASE_CURRENT.md`
  - `KNOWN_ISSUES.md`
  - `docs/adr/ADR-001-control-operativo-del-proyecto.md`
  - plantillas operativas en `docs/templates/`
  - scripts de verificación única `scripts/verify_all.sh` y `scripts/verify_all.ps1`

Objetivo: hacer explícitos fase activa, deuda, gates, decisiones y validación antes de continuar con nuevas features.

## 2026-06-05 — B38-FIX-01 AI Command Bar real

### Corregido

- La command bar de Creación deja de generar plantillas fijas como éxito de producción.
- Se separa el pipeline en clasificación, planificación, ejecución provider-backed y staging de resultados.
- El prompt exacto del usuario viaja al provider como instrucción principal.
- Si no hay provider IA real configurado, el job falla claramente en vez de simular contenido.
- Se añade panel `Jobs` / `Tareas IA` con progreso por fases, estado, cancelación y ver resultado.
- Los resultados siguen siendo candidatos/informes revisables; no hay canon automático.

### Validación

- Tests B38 específicos cubren sensibilidad al prompt, clasificación, lifecycle, errores, resultados y UI.
- Checklist Windows: `docs/validation/b38-fix-01-ai-command-bar-windows-smoke.md`.

## 2026-06-05 — B38 Command bar IA y jobs revisables

Commits relevantes:

- `2c877cf` — contrato UI B38.
- `d6e63a2` — barra superior Creación, panel de capas persistente, command bar IA y contrato AIJob.
- `f2a2cd5` — runner no bloqueante, dispatch, resultados revisables y candidatos.

Estado:

- Implementado y validado en WSL/offscreen.
- Validación visual Windows nativa pendiente.

Cambios clave:

- Command bar IA inferior en Creación.
- Jobs IA in-memory no bloqueantes.
- Resultados pasan a panel/bandeja revisable.
- Nada se canoniza automáticamente.

## 2026-06-04 — B36 Worldbuilding por capas causales

Cierre: `docs/cierres/bloque-36-cierre.md`

Estado:

- Implementado en WSL.
- Validación Windows nativa pendiente.

Cambios clave:

- Vista por capas causales si Worldbuilding ON.
- Asignación de capas en nodos/árboles.
- Relaciones causales.
- Acciones IA descendente/ascendente como sugerencias.
- Coherencia B35 usa contexto causal.

## Bloques recientes previos

| Bloque | Resumen | Evidencia |
|---|---|---|
| B35 | Coherencia de subgrafo, reparación y candidatos | `docs/cierres/bloque-35-coherencia-subgrafo.md` |
| B34 | Árboles jerárquicos y contexto IA | `docs/cierres/bloque-34-arboles-jerarquicos.md` |
| B33 | Creación MVP estable | `docs/cierres/bloque-33-creacion-mvp.md` |
| B31 | UX Desktop | `docs/cierres/bloque-31-cierre.md` |
| B30 | Gate/cierre contractual | `docs/cierres/bloque-30-cierre.md` |

## Regla de mantenimiento

Al cerrar un bloque significativo:

1. Añadir entrada fechada.
2. Enlazar cierre técnico o checklist.
3. Indicar validaciones reales.
4. Indicar deuda/Windows pendiente si aplica.
5. No inventar resultados no ejecutados.
