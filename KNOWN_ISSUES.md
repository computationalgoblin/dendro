# KNOWN_ISSUES — Deuda y bugs conocidos

Última actualización: 2026-06-07

Este archivo es el índice operativo de deuda visible. No renumera ni reemplaza fuentes históricas.

Fuentes principales:

- `docs/product/product_debt_map.md`
- `docs/deuda_consolidada_B01_B24.md`
- `docs/deuda_consolidada_B01_B28.md`
- `docs/cierres/`
- `docs/validation/`
- `docs/agents/HANDOFF.md`
- memoria operativa del proyecto confirmada en sesiones previas

## Convenciones

| Campo | Uso |
|---|---|
| ID | No renumerar IDs existentes. Deuda nueva usa `DC-XXX`, `DC-BXX-*`, `DC-WIN-*` o prefijo documental explícito. |
| Estado | abierta, mitigada, cerrada, absorbida, ambigua, pendiente-validación |
| Severidad | bloqueante, media, baja |
| Criterio de cierre | Evidencia concreta necesaria. |

Regla: **mitigada no significa resuelta**.

## Bugs confirmados por validación visual Windows (2026-06-07)

Resultado: 95 checks, 41 PASA, 11 FALLA, 0 PARCIAL, 43 N/A.
Informe: `docs/pruebas/resultados/resultado_B30_B43_*.txt`

| ID | Estado | Severidad | Origen | Descripción | Causa raíz | Criterio de cierre |
|---|---|---|---|---|---|---|
| BUG-B34-PANEL | fix-aplicado | alta | B34 | Panel de detalle no aparece al seleccionar una Rama. | `_notify_canvas_selected()` emite selección al view. `shape()` incluye rect completo cuando colapsado. | Validar en Windows. |
| BUG-B34-BADGE | fix-aplicado | media | B34 | Badge de miembros flota fuera al colapsar rama. | `_collapse()` oculta `_count_item`, `_expand()` restaura. | Validar en Windows. |
| BUG-B34-RELINT | fix-aplicado | alta | B34 | No se puede crear relación entre nodos internos y su rama contenedora. | `shape()` incluye rect completo cuando colapsado + `_notify_canvas_selected`. | Validar en Windows. |
| BUG-B34-CYCLE | fix-aplicado | alta | B34 | Prevención de ciclos no funciona (sólo feedback visual rojo). | `mouseReleaseEvent` bloquea emit si `would_create_cycle()`. | Validar en Windows. |
| BUG-B35-REPAIR | fix-aplicado | alta | B35 | Reparación de coherencia: preview no editable, no persiste, se pierde al cerrar drawer. | Preview editable + stash en `ctx` sobrevive drawer close + restore on reopen. | Validar en Windows. |
| BUG-B36-WB | fix-aplicado | alta | B36 | Toggle Worldbuilding no activa capas en el grafo. | `set_worldbuilding_active(active)` propagado en ambos sentidos. | Validar en Windows. |
| BUG-B36-TYPO | fix-aplicado | alta | B36 | Botón "Crear anillo desde rama" nunca aparece. | `worldbuilding_enabled` → `worldbuilding_active`. | Validar en Windows. |
| BUG-B37-FOCUS | fix-aplicado | media | B37 | Focus vecindad hace desaparecer todo. | `focus_neighborhood` incluye ancestros contenedores via `_membership`. | Validar en Windows. |
| BUG-B37-CAM | no-era-bug | — | B37 | Zoom/pan no funcionaba. | `wheelEvent` + `ScrollHandDrag` ya existen; era síntoma de BUG-B37-FOCUS. | Re-verificar tras fix FOCUS. |
| BUG-B38-ERROR | fix-aplicado | baja | B38 | Error de provider no visible/prominente en UI. | Error en rojo durante 8s con `QTimer` que restaura estilo. | Validar en Windows. |

## Pendientes de validación Windows — actualizados tras prueba 2026-06-07

| ID | Estado | Severidad | Origen | Descripción | Criterio de cierre |
|---|---|---|---|---|---|
| DC-WIN-B30-B35 | cerrada | — | B30-B35 | Validación visual Windows ejecutada 2026-06-07: B30-B33 PASA, B34 con bugs (ver arriba), B35 con bug reparación. | Bugs B34/B35 resueltos. |
| DC-WIN-B36 | reabierta | alta | B36 | Bug confirmado: toggle worldbuilding no propaga al canvas + typo atributo. | BUG-B36-WB y BUG-B36-TYPO cerrados. |
| DC-WIN-B37 | reabierta | media | B37 | Bugs confirmados: focus vecindad y cámara. | BUG-B37-FOCUS y BUG-B37-CAM cerrados. |
| DC-WIN-B38 | mitigada | baja | B38 | Command bar funciona; error provider es gap de testabilidad, no bug funcional. | Mejorar prominencia de errores IA. |
| DC-WIN-B39 | cerrada | — | B39 | Labels/controles validados OK en Windows. | — |
| DC-WIN-B40 | cerrada | — | B40 | Wizard, config, presets validados OK en Windows. | — |
| DC-WIN-B41 | pendiente-validación | media | B41 | Milestones causales: no se pudo probar (N/A en prueba, worldbuilding no funcional). | Revalidar tras fix B36. |
| DC-WIN-B42 | pendiente-validación | baja | B42 | Hardening IA: no se pudo probar sin provider real configurado. | Smoke IA con provider real. |
| DC-WIN-B43 | pendiente-validación | baja | B43 | Prompt Registry: N/A (sin provider real). | Smoke IA inline con provider real. |
| DC-B28-UI-WIN | abierta | media | B28 | B28 sin validación Desktop nativa Windows según deuda histórica. | Validación Windows documentada. |

## Deuda documental/operativa reciente

| ID | Estado | Severidad | Origen | Descripción | Criterio de cierre |
|---|---|---|---|---|---|
| DOC-B37-CIERRE | cerrada | baja | B37 | Cierre técnico dedicado creado en `docs/cierres/bloque-37-cierre.md`. | Cerrada documentalmente; no implica Windows OK. |
| DOC-B38-CIERRE | cerrada | baja | B38 | Cierre técnico dedicado creado en `docs/cierres/bloque-38-cierre.md`. | Cerrada documentalmente; no implica Windows OK. |
| DOC-B39-CIERRE | cerrada | baja | B39 | Cierre técnico dedicado creado en `docs/cierres/bloque-39-cierre.md`. | Cerrada documentalmente; no implica Windows OK. |
| DOC-B41-B43-CIERRE | cerrada | baja | B41-B43 | Cierres técnicos dedicados creados en `docs/cierres/bloque-41-cierre.md`, `docs/cierres/bloque-42-cierre.md` y `docs/cierres/bloque-43-cierre.md`. | Cerrada documentalmente; no implica Windows OK. |

## Deuda activa de producto/técnica

| ID | Estado | Severidad | Origen | Descripción | Destino/Criterio de cierre |
|---|---|---|---|---|---|
| DC-026 | abierta | baja | B17 | `import review edit` no implementado. | Implementar en bloque de importación o descartar con decisión explícita. |
| DC-027 | abierta | baja | B17 | `import review merge` no implementado; estado `FUSIONADO` existe pero sin operación. | Implementar operación o retirar contrato muerto. |
| DC-028 | abierta | baja | B17 | `PDFExtractor` requiere `pymupdf` no incluido como dependencia. | Registrar dependencia o documentar skip permanente. |
| DC-033 | abierta | baja | B18 | `get_ordered_events` no maneja `partial_order` real ni ciclos. | Implementar orden parcial/ciclos con tests. |
| DC-034 | abierta | baja | B18/B27 | `TimelineEvent` sin sincronización automática con `NarrativeEntity(EVENTO)`. | Decidir integración o mantener separación mediante ADR. |
| DC-035 | abierta | baja | B19/B27 | IA writing usa provider simulado/fallback en flujos antiguos. | Validar provider real o documentar fallback como modo offline. |
| DC-036 | abierta | baja | B19/B27 | `get_tree` recursivo no escala para más de 1000 unidades. | Refactor iterativo/cache y benchmark. |
| DC-040 | abierta | baja | B21 | Flakes CLI secrets/clues por subprocess en histórico. | Reproducir o cerrar con evidencia de suite estable. |
| DC-044 | abierta | baja | B24/B27 | `improvise` usa fallback determinista. | Provider real o contrato explícito de modo simulado. |
| DC-045 | abierta | media | B25 | `AnalysisService` sin tests unitarios dedicados según consolidación. | Añadir tests dedicados o verificar cobertura existente real. |

## Deuda de layout/grafo reciente

| ID | Estado | Severidad | Origen | Descripción | Criterio de cierre |
|---|---|---|---|---|---|
| DC-034-01 | abierta | baja | B34 | Layout de contenedores no persiste posiciones entre sesiones. | Persistencia layout validada save/reopen. |
| DC-034-02 | abierta | baja | B34 | `_tree_context` sin cache; puede ser lento en proyectos grandes. | Cache/benchmark o decisión documentada. |
| DC-034-03 | abierta | baja | B34 | Collapse/expand visual se pierde al refrescar grafo; era intencional/MVP. | Decidir si estado debe ser persistente o efímero. |
| DC-034-04 | abierta | media | B34 | Layout jerárquico Windows imperfecto en collapse/expand anidado y relaciones. | Pasada graph layout/scene graph con prueba Windows. |

## Deuda ambigua histórica

| ID | Estado | Severidad | Fuente | Nota |
|---|---|---|---|---|
| DC-001 — DC-007 | ambigua | baja | `docs/deuda_consolidada_B01_B24.md` | Sin evidencia documental individual disponible. |
| DC-010 — DC-015 | ambigua | baja | `docs/deuda_consolidada_B01_B24.md` | Sin evidencia documental individual disponible. |
| DC-017 — DC-021 | ambigua | baja | `docs/deuda_consolidada_B01_B24.md` | Sin evidencia documental individual disponible. |
| DC-023 | ambigua | baja | `docs/deuda_consolidada_B01_B24.md` | Sin evidencia documental individual disponible. |

## Deuda cerrada/absorbida relevante

| ID | Estado | Cerrada en | Evidencia |
|---|---|---|---|
| DC-008 | cerrada | B05 | Prompt histórico del usuario. |
| DC-009 | cerrada | B06 | `tests/qa/test_dc009_coverage.py`. |
| DC-016 | absorbida | B12 | Prompt histórico del usuario. |
| DC-022 | cerrada | B15.8 | `tests/application/test_candidate_service.py`. |
| DC-024 | cerrada | B15.8 | `tests/application/test_orchestrator_service.py`. |
| DC-029 | cerrada | B17.1 | Idempotencia reject import candidate. |
| DC-030 | cerrada | B17.1 | `_save()` muerto en ImportService. |
| DC-031 | cerrada | B17.1 | Preservación `proposed_relations`. |
| DC-032 | cerrada | B17.1 | Persistencia real import baskets. |

## Regla de actualización

- Toda deuda nueva debe incluir origen, impacto y criterio de cierre.
- No cerrar deuda sin test, smoke, ADR o validación manual documentada.
- No renumerar deuda antigua aunque sea fea.
- Si un ID histórico tiene significado ambiguo, crear entrada nueva en vez de sobrescribirlo.
