# Product Debt Map — Dendro / Narrative Architect (BETA baseline)

Última actualización: 2026-06-13 — I08 PDF desktop dependency.

## Deuda activa

| ID | Descripción | Prioridad | Estado | Origen |
|----|-------------|-----------|--------|--------|
| DC-001..DC-024 | Sin evidencia documental individual | baja | abierta | B01-B16 |
| DC-026 | import review edit no implementado | baja | abierta | B17 |
| DC-027 | import review merge no implementado | baja | abierta | B17 |
| DC-033 | get_ordered_events sin partial_order real | baja | abierta | B27 |
| DC-034 | TimelineEvent sync con NarrativeEntity(EVENTO) | baja | abierta | B27 |
| DC-035 | IA writing provider simulado | baja | abierta | B27 |
| DC-036 | get_tree no escala >1000 entidades | baja | abierta | B27 |
| DC-040 | CLI flakes secrets/clues | baja | abierta | — |
| DC-044 | improvise fallback determinista | baja | abierta | B27 |
| DC-045 | AnalysisService sin tests unitarios | media | abierta | B25 |
| DC-B28-UI-WIN | B28 sin validación Desktop Windows | media | abierta | B28 |
| DC-034-01 | Layout contenedores no persiste posiciones | baja | abierta | B34 |
| DC-034-02 | _tree_context sin cache | baja | abierta | B34 |
| DC-034-03 | Collapse/expand se pierde al refrescar | baja | abierta | B34 |
| DC-034-04 | Layout jerárquico Windows imperfecto | media | abierta | B34 |

## Deuda cerrada

| ID | Descripción | Cerrada en |
|----|-------------|------------|
| DC-008 | Sin detalle | B05 |
| DC-009 | Persistencia v5 tests history | B06 |
| DC-016 | Absorbida | B12 |
| DC-022 | CandidateService sin tests | B15.8 |
| DC-024 | OrchestratorService sin tests | B15.8 |
| DC-028 | PDFExtractor requiere pymupdf | BETA1-I08 |

## Reglas

- No renumerar IDs.
- "Mitigado" != "resuelto".
- Toda deuda nueva: DC-{bloque}-{secuencial}.
