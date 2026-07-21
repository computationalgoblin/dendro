# Product Debt Map — Dendro / Narrative Architect (BETA baseline)

Última actualización: 2026-07-21 (cierre de beta) — **cero deuda abierta**: DC-AUDIT-03 saldada (puertos), DC-AUDIT-02 cerrada (validación efectiva por flujo), DC-040 mitigada (sharding del runner), DC-001..024 descartadas por prescripción.

## Deuda activa

| ID | Descripción | Prioridad | Estado | Origen |
|----|-------------|-----------|--------|--------|
| DC-001..DC-024 | Sin evidencia documental individual | baja | descartadas por prescripción (2026-07-21, cierre de beta): heredadas de B01-B16 sin evidencia reproducible ni síntoma vigente; reabrir solo con evidencia concreta | B01-B16 |
| DC-026 | import review edit no implementado | baja | obsoleta — subsistema de importación retirado (BETA1-CLEANUP-IMPORT) | B17 |
| DC-027 | import review merge no implementado | baja | obsoleta — subsistema de importación retirado (BETA1-CLEANUP-IMPORT) | B17 |
| DC-033 | get_ordered_events sin partial_order real | baja | descartada — decisión de producto 2026-07-03 (Timeline/Redacción sin superficie GUI; solo CLI) | B27 |
| DC-034 | TimelineEvent sync con NarrativeEntity(EVENTO) | baja | descartada — decisión de producto 2026-07-03 (Timeline/Redacción sin superficie GUI; solo CLI) | B27 |
| DC-035 | IA writing provider simulado | baja | descartada — decisión de producto 2026-07-03 (fallback de test legítimo; Redacción sin GUI) | B27 |
| DC-036 | get_tree no escala >1000 entidades | baja | descartada — decisión de producto 2026-07-03 (Timeline/Redacción sin superficie GUI; solo CLI) | B27 |
| DC-040 | CLI flakes secrets/clues | baja | mitigada (2026-07-21): los flakes solo aparecían bajo ordenación de suite completa (estado global de sesión compartido); el runner (`scripts/run_all_tests.py`) ejecuta las suites en subprocesos separados y los tests pasan aislados. Aceptada como cerrada para beta; reabrir si reaparece bajo el runner | — |
| DC-044 | improvise fallback determinista | baja | obsoleta — su único consumidor (LiveModeService) está fuera del runtime desktop desde BETA1-H13 | B27 |
| DC-B28-UI-WIN | B28 sin validación Desktop Windows | media | descartada — decisión de producto 2026-07-03 (no se hará pasada formal; la validación queda en el uso real en Windows) | B28 |
| DC-034-01 | Layout contenedores no persiste posiciones | baja | descartada — decisión de producto 2026-07-03 | B34 |
| DC-034-02 | _tree_context sin cache | baja | descartada — decisión de producto 2026-07-03 (interno; reabrir solo si hay lentitud medible) | B34 |
| DC-034-03 | Collapse/expand se pierde al refrescar | baja | descartada — decisión de producto 2026-07-03 | B34 |
| DC-034-04 | Layout jerárquico Windows imperfecto | media | descartada — decisión de producto 2026-07-03 (sin bugs reproducibles; reabrir con evidencia) | B34 |
| DC-UX4-HITO | editar:hito no aplica | media | cerrada (causa real: el hito seleccionado no llegaba al contexto; se inyecta `selected_milestones` + `_apply_edit` edita `year`; verificado en real 1200→1300) | UX4 |
| DC-AUDIT-01 | La GUI no tiene punto de exportación (al retirar la vista de import/export desapareció su único consumidor; ExportService sigue vivo y accesible solo por CLI `export`) | media | descartada — decisión de producto 2026-07-03: la exportación queda vía CLI `narrative-architect export` | AUDIT-01 |
| DC-AUDIT-02 | output_schema_validator no cubre los AIJobType nuevos y la ruta principal de jobs llama al gateway con validate=False (la validación efectiva la hace _extract_json/stage_results) | baja | cerrada (2026-07-21): tras el recorte post-WIKI la validación efectiva es POR FLUJO y dedicada — `watering_payload` (riego), `memory_payload` (memoria), `stage_results`/`_extract_json` (semillas), parseo acotado del navegador wiki — y ningún caller vivo usa `validate=True`; el validador genérico queda como opción del gateway. No se ampliará su cobertura | AUDIT-03 |
| DC-AUDIT-03 | Violaciones de capas congeladas en DOCUMENTED_LAYER_DEBT (tests/architecture): application importaba infrastructure.ai_provider y persistence.store/schema | media | SALDADA (2026-07-21) — puertos en application: `ai_provider_port.py` (contrato AIProvider + provider_chat + `resolve_provider` por import dinámico; infrastructure re-exporta por compatibilidad) y `repository_port.py` (Protocol `ProjectRepository` + `default_repository` + `current_schema_version` por import dinámico). `DOCUMENTED_LAYER_DEBT` queda vacío y el guard corre sin allowlist | AUDIT-03 |

## Deuda cerrada

| ID | Descripción | Cerrada en |
|----|-------------|------------|
| DC-008 | Sin detalle | B05 |
| DC-009 | Persistencia v5 tests history | B06 |
| DC-016 | Absorbida | B12 |
| DC-022 | CandidateService sin tests | B15.8 |
| DC-024 | OrchestratorService sin tests | B15.8 |
| DC-028 | PDFExtractor requiere pymupdf (dependencia retirada de pyproject en BETA1-AUDIT-01 al eliminarse PDFExtractor) | BETA1-I08 |
| DC-045 | AnalysisService sin tests unitarios | BETA1-H01 |

## Reglas

- No renumerar IDs.
- "Mitigado" != "resuelto".
- Toda deuda nueva: DC-{bloque}-{secuencial}.
