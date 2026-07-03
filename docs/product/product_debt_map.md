# Product Debt Map — Dendro / Narrative Architect (BETA baseline)

Última actualización: 2026-07-03 — auditoría general (BETA1-AUDIT-01..04); retirada de pymupdf (deuda inversa de DC-028) y registro de DC-AUDIT-01.

## Deuda activa

| ID | Descripción | Prioridad | Estado | Origen |
|----|-------------|-----------|--------|--------|
| DC-001..DC-024 | Sin evidencia documental individual | baja | abierta | B01-B16 |
| DC-026 | import review edit no implementado | baja | obsoleta — subsistema de importación retirado (BETA1-CLEANUP-IMPORT) | B17 |
| DC-027 | import review merge no implementado | baja | obsoleta — subsistema de importación retirado (BETA1-CLEANUP-IMPORT) | B17 |
| DC-033 | get_ordered_events sin partial_order real | baja | abierta | B27 |
| DC-034 | TimelineEvent sync con NarrativeEntity(EVENTO) | baja | abierta | B27 |
| DC-035 | IA writing provider simulado | baja | abierta | B27 |
| DC-036 | get_tree no escala >1000 entidades | baja | abierta | B27 |
| DC-040 | CLI flakes secrets/clues | baja | abierta | — |
| DC-044 | improvise fallback determinista | baja | abierta | B27 |
| DC-B28-UI-WIN | B28 sin validación Desktop Windows | media | abierta | B28 |
| DC-034-01 | Layout contenedores no persiste posiciones | baja | abierta | B34 |
| DC-034-02 | _tree_context sin cache | baja | abierta | B34 |
| DC-034-03 | Collapse/expand se pierde al refrescar | baja | abierta | B34 |
| DC-034-04 | Layout jerárquico Windows imperfecto | media | abierta | B34 |
| DC-UX4-HITO | editar:hito no aplica | media | cerrada (causa real: el hito seleccionado no llegaba al contexto; se inyecta `selected_milestones` + `_apply_edit` edita `year`; verificado en real 1200→1300) | UX4 |
| DC-AUDIT-01 | La GUI no tiene punto de exportación (al retirar la vista de import/export desapareció su único consumidor; ExportService sigue vivo y accesible solo por CLI `export`) | media | abierta | AUDIT-01 |
| DC-AUDIT-02 | output_schema_validator no cubre los AIJobType nuevos y la ruta principal de jobs llama al gateway con validate=False (la validación efectiva la hace _extract_json/stage_results) | baja | abierta | AUDIT-03 |

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
