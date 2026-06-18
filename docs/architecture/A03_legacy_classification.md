# A03 — Clasificación de vistas y controladores legacy (BETA 1)

> Actualización BETA1-H02 (2026-06-15): las piezas marcadas como
> DESCONECTADO en A01/A02/A03 fueron eliminadas físicamente del Desktop
> runtime, salvo dependencias compartidas documentadas como `SessionController`.
> Este documento conserva la clasificación histórica que justificó el borrado.

Fecha: 2026-06-11 · Rama: `feature/BETA1-A03` · Tickets previos: A01, A02

Contrato BETA 1: el runtime solo expone Home y Creación (con Física e IA/RAG
como capacidades internas de Creación). Este documento clasifica cada vista y
controlador del host de escritorio según su relación con ese contrato.

Categorías:

- **RUNTIME**: se instancia y se usa en el runtime BETA 1.
- **COMPARTIDO**: se instancia solo como dependencia de un componente RUNTIME.
- **DESCONECTADO**: código intacto, instanciación eliminada en Fase A.
  Candidato a reactivación en fases futuras (Galería/Sesión post-BETA 1).
- **LEGACY INTERNO**: clase definida pero sin instanciador en el runtime;
  no se borra en Fase A.

## Vistas (`hosts/DesktopHostPySide/views/`)

| Módulo / Clase | Categoría | Notas |
|---|---|---|
| `home_view.py` · `HomeView`, `HomeNode`, `QuietIconButton` | RUNTIME | Home BETA 1, solo card Creación |
| `home_view.py` · `_BranchLine`, método `_branch_line`, tonos `gallery`/`session` en `HomeNode._apply_tone_style` | LEGACY INTERNO | Sin uso tras A01. No cumplen condición de borrado en A03 (decorativos, sin riesgo); borrado propuesto para limpieza post-Fase A |
| `workspaces.py` · `CreationWorkspace` + paneles (`RingInfoPanel`, `EntityQuickCreatePanel`, `SourceQuickCreatePanel`, `LayerQuickCreatePanel`, `CandidateReviewPanel`, `SuggestionInboxPanel`, `NarrativeWorkbench`, `AIJobsPanel`, `AIJobResultPanel`, `_AIJobWorker`, `CreationSearchPanel`, `CreationFilterPanel`, `_LayerEdgeFlyout`, `CausalMilestonePanel`, `_SuggestWorker`, `_SimpleFormPanel`) | RUNTIME | Núcleo de Creación; incluye integración IA (jobs, sugerencias) |
| `workspaces.py` · `GalleryWorkspace` | DESCONECTADO (A01) | Sin instanciador desde A01 |
| `workspaces.py` · `SessionWorkspace`, `SessionPreparationWorkspace`, `SessionOverview` | DESCONECTADO (A01) | `SessionPreparationWorkspace` y `SessionOverview` solo se instancian dentro de `SessionWorkspace` |
| `corpus_view.py`, `relation_view.py`, `candidate_view.py`, `import_export_view.py`, `source_view.py`, `layer_view.py` | RUNTIME | Consumidas por `CreationWorkspace` |
| `writing_view.py`, `framework_view.py` | RETIRADO (H09/H10) | Escritura y frameworks salen del runtime Desktop BETA1; dominio/schema quedan para migración posterior |
| `timeline_view.py` | RETIRADO (H14) | TimelineEvent sale del runtime Desktop; cronología viva sigue en hitos causales y ProjectChronology |
| `campaign_view.py` · `CampaignView`, `FactionFrontView`, `SecretsCluesView` | DESCONECTADO (A02) | Solo las consumía `SessionWorkspace` |
| `corpus_view.py` · filtros/creación legacy `faccion`, `secreto`, `pista` | RETIRADO (H11/H12) | Corpus técnico solo crea/filtra tipos BETA1 visibles: personaje, objeto, nota |
| `session_view.py` · `SessionView` | DESCONECTADO (A02) | Ídem |
| `live_post_view.py` · `LivePostView` | DESCONECTADO (A02) | Ídem |
| `issues_history_view.py` · `IssuesHistoryView` | DESCONECTADO (A02) | Ídem |
| `creation_parts/` | — | Directorio vacío a fecha de A03 |

## Controladores (`hosts/DesktopHostPySide/controllers/`)

| Controlador | Categoría | Instanciador | Notas |
|---|---|---|---|
| `project_controller` | RUNTIME | MainWindow | Núcleo proyecto |
| `ai_controller` | RUNTIME | MainWindow | IA: settings, provider, Creación. No tocado (regla A03) |
| `ai_context_controller` | RUNTIME | `CreationWorkspace` | Dependencia IA del runtime. Solo clasificado, no tocado |
| `causal_milestone_controller` | RUNTIME | `CreationWorkspace` | Hitos causales en Creación |
| `entity_controller`, `relation_controller`, `candidate_controller`, `source_controller`, `layer_controller` | RUNTIME | MainWindow | Consumidos por vistas de Creación |
| `writing_controller`, `framework_controller` | RETIRADO (H09/H10) | Sus únicas vistas Desktop se retiraron del runtime; servicios internos se conservan |
| `timeline_controller` | RETIRADO (H14) | Su única vista Desktop (`TimelineView`) fue retirada; `TimelineService` queda para migración |
| `import_controller` | RUNTIME | `ImportExportView` (propia instancia) | La instancia duplicada `MainWindow.ic` se desconecta en A03 |
| `session_controller` | RETIRADO (H13) | Export Desktop ya no expone sesión/campaña; `ExportService` se instancia sin `SessionService` |
| `issue_controller` | DESCONECTADO (A03) | — | Único consumidor: `IssuesHistoryView` (desconectada en A02) |
| `live_mode_controller` | DESCONECTADO (A03) | — | Único consumidor: `LivePostView` (A02) |
| `post_session_controller` | DESCONECTADO (A03) | — | Único consumidor: `LivePostView` (A02) |
| `campaign_controller` | DESCONECTADO (A03) | — | Único consumidor: `CampaignView` (A02) |
| `secrets_controller` | DESCONECTADO (A03) | — | Único consumidor: `SecretsCluesView` (A02). Nota: `LiveModeController` usaba `sc.sec`, también desconectado |
| `faction_controller` | DESCONECTADO (A03) | — | Único consumidor: `FactionFrontView` (A02) |
| `ProjectController.counts` · contadores `secrets/clues/factions/fronts` | RETIRADO (H11/H12) | El resumen normal solo muestra núcleo BETA1; colecciones legacy permanecen en persistencia |

Verificación de seguridad: grep en `hosts/` y `tests/` confirma cero
referencias a `self.issuec/lmc/psc/ic/ccamp/secretsc/factionc` fuera de su
construcción, y ningún test instancia `MainWindow`.

## No tocado (fuera de alcance A03)

- `packages/domain/*`, `packages/application/*`, `packages/persistence/*`:
  los servicios de dominio que usaban los controladores desconectados
  (sesión, secretos, facciones, incidencias, live) permanecen íntegros.
- `widgets/graph_canvas.py` (física/canvas): intacto, incluidos los 7 tests
  B37/B44 rotos en baseline (deuda fases B/C).
- IA/RAG: solo clasificación de dependencia (`ai_controller`,
  `ai_context_controller` = RUNTIME).

## Deuda registrada

1. `test_b27_5_shell_keeps_three_product_spaces` codifica el shell pre-BETA 1
   (3 espacios). Actualizar contrato del test en A04: shell BETA 1 = Home +
   Creación.
2. 7 tests B37/B44 (graph canvas) rotos en baseline → fases B/C.
3. Borrado físico de código DESCONECTADO/LEGACY INTERNO: decisión post-Fase A.
4. Docstrings con referencias a "three spaces"/B31 en `home_view.py` y
   `main_window.py` → A04.
5. Warnings de runtime observados en smoke A02 (stylesheet `HomeNode`, spam
   `QPainter`, layout `concentric_rings` persistido con `project=None`) →
   auditar en A04.
