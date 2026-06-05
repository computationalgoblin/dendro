# KNOWN_ISSUES — Deuda y bugs conocidos

Última actualización: 2026-06-05

Este archivo es el índice operativo de deuda visible. No renumera ni reemplaza fuentes históricas.

Fuentes principales:

- `docs/product/product_debt_map.md`
- `docs/deuda_consolidada_B01_B24.md`
- `docs/deuda_consolidada_B01_B28.md`
- `docs/cierres/`
- `docs/validation/`
- memoria operativa del proyecto confirmada en sesiones previas

## Convenciones

| Campo | Uso |
|---|---|
| ID | No renumerar IDs existentes. Deuda nueva usa `DC-XXX` o `DC-BXX-*`. |
| Estado | abierta, mitigada, cerrada, absorbida, ambigua, pendiente-validación |
| Severidad | bloqueante, media, baja |
| Criterio de cierre | Evidencia concreta necesaria. |

Regla: **mitigada no significa resuelta**.

## Pendientes críticos de validación visual Windows

| ID | Estado | Severidad | Origen | Descripción | Criterio de cierre |
|---|---|---|---|---|---|
| DC-WIN-B36 | pendiente-validación | media | B36 | Worldbuilding por capas causales implementado en WSL; prueba visual Windows nativa pendiente. | Usuario ejecuta smoke Windows y confirma comportamiento o abre bugs específicos. |
| DC-WIN-B37 | pendiente-validación | media | B37 | Creación a escala/filtros/flyout implementado en WSL; validación Windows nativa pendiente. | Usuario valida UI nativa Windows. |
| DC-WIN-B38 | pendiente-validación | media | B38 | Command bar IA/jobs revisables implementado en WSL; checklist Windows pendiente. | Completar `docs/validation/b38-command-bar-windows-smoke.md`. |
| DC-B28-UI-WIN | abierta | media | B28 | B28 sin validación Desktop nativa Windows según deuda histórica. | Validación Windows documentada o reemplazada por bloque de hardening visual. |

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
