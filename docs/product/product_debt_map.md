# Product Debt Map — Dendro / Narrative Architect

Última actualización: B34 completado, B35 pendiente.

## Convenciones

- **ID**: DC-{bloque}-{secuencial} para deuda de bloque, DC-{global} para deuda transversal.
- **Prioridad**: bloqueante / media / baja.
- **Estado**: abierta / mitigada / cerrada.
- **Destino**: bloque o hito donde se planea resolver.

## Deuda activa

| ID | Descripción | Prioridad | Estado | Origen | Destino |
|----|-------------|-----------|--------|--------|---------|
| DC-001..DC-024 | Sin evidencia documental individual (rango arrastrado desde B1-B16) | baja | abierta | B01-B16 | Sin destino |
| DC-026 | import review edit no implementado | baja | abierta | B17 | B26+ |
| DC-027 | import review merge no implementado | baja | abierta | B17 | B26+ |
| DC-028 | PDFExtractor requiere pymupdf no en dependencias | baja | abierta | B17 | B26+ |
| DC-033 | get_ordered_events sin partial_order real | baja | abierta | B27 | B29+ |
| DC-034 | TimelineEvent sync con NarrativeEntity(EVENTO) | baja | abierta | B27 | B29+ |
| DC-035 | IA writing provider simulado, falta integración real | baja | abierta | B27 | B27+ |
| DC-036 | get_tree no escala >1000 entidades | baja | abierta | B27 | B29+ |
| DC-040 | CLI flakes secrets/clues (5) | baja | abierta | — | hardening |
| DC-044 | improvise fallback determinista | baja | abierta | B27 | B27+ |
| DC-045 | AnalysisService sin tests unitarios dedicados | media | abierta | B25 | B29+ |
| DC-B28-UI-WIN | B28 sin validación Desktop nativa Windows | media | abierta | B28 | B30+ |
| DC-034-01 | Layout contenedores no persiste posiciones entre sesiones | baja | abierta | B34 | Futuro |
| DC-034-02 | _tree_context NarrativeContextBuilder sin cache, lento en proyectos grandes | baja | abierta | B34 | Futuro |
| DC-034-03 | Collapse/expand visual se pierde al refrescar grafo (intencional) | baja | abierta | B34 | Futuro |
| DC-034-04 | Layout jerárquico Windows imperfecto: artefactos en collapse/expand anidado, relaciones inconsistentes, degradación de layout en algunos casos | media | abierta | B34 | Pasada graph layout/scene graph |

## Deuda cerrada

| ID | Descripción | Cerrada en | Notas |
|----|-------------|------------|-------|
| DC-008 | Sin detalle | B05 | Cerrada por usuario |
| DC-009 | Persistencia v5 tests history | B06 | test_dc009_coverage.py |
| DC-016 | Absorbida | B12 | Absorbida en B12 |
| DC-022 | CandidateService sin tests | B15.8 | test_candidate_service.py |
| DC-024 | OrchestratorService sin tests | B15.8 | test_orchestrator_service.py |

## Regla

- No renumerar IDs.
- "Mitigado" != "resuelto".
- Toda deuda nueva sigue el formato DC-{bloque}-{secuencial}.
