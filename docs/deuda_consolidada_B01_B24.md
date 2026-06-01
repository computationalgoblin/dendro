# Deuda consolidada B01→B24

**Fecha:** 2026-05-31
**Fuentes:** cierres B17-B24, HANDOFF.md, tests/qa/, tests/application/
**Método:** búsqueda exhaustiva de referencias DC en todo /workspace/docs y /workspace/tests

---

## 1. Resumen ejecutivo

| Métrica | Valor |
|---------|-------|
| Total DC detectadas | 44 (DC-001 → DC-044) |
| Abiertas | 20 |
| Cerradas | 11 |
| Absorbidas | 1 |
| Ambigüas (sin evidencia documental) | 17 |
| Duplicadas (HANDOFF vs B17) | 5 |
| Descartadas | 0 |
| Críticas | 0 |
| Medias | 6 (cerradas 4, abiertas 1, ambigua 1) |
| Bajas | 21 abiertas + 17 ambiguas |
| Informativas | 0 |

**Nota:** DC-001 a DC-024 no tienen definición individual en ningún documento disponible (cierres B1-B16 no existen en el repositorio). Solo se referencian como rango "DC-001..DC-024: Sin cambios (arrastrada)" en cierres B18+. Se marcan como **ambiguas** hasta que se recupere la fuente original.

---

## 2. Tabla maestra DC

| ID | Estado | Gravedad | Origen | Última mención | Descripción normalizada | Evidencia / notas | Destino natural | Ticket propuesto |
|----|--------|----------|--------|-----------------|------------------------|-------------------|-----------------|------------------|
| DC-001 — DC-007 | ambigua | baja | B01-B07 | B24 cierre (rango arrastrado) | Sin evidencia documental individual. Definidas en cierres B1-B7 no disponibles. | Solo aparecen como rango "DC-001..DC-041" en cierres B18-B24. | sin destino | Recuperar cierres antiguos o marcar como descartadas |
| DC-008 | cerrada | baja | B05 | B05 | Cerrada en B05 según prompt del usuario. Sin cierre disponible. | Evidencia: prompt del usuario "DC-008 cerrada en B05". | cerrada | — |
| DC-009 | cerrada | baja | B06 | B06 (test_dc009_coverage.py) | Persistencia v5 y tests de history dedicados. | `tests/qa/test_dc009_coverage.py` — test implementado en B06-T03. | cerrada | — |
| DC-010 — DC-015 | ambigua | baja | B07-B11 | B24 cierre (rango arrastrado) | Sin evidencia documental individual. | Solo aparecen como rango en cierres B18-B24. | sin destino | Recuperar cierres antiguos |
| DC-016 | absorbida | baja | B12 | B12 | Absorbida en B12 según prompt del usuario. Sin cierre disponible. | Evidencia: prompt del usuario "DC-016 absorbida en B12". | absorbida | — |
| DC-017 — DC-021 | ambigua | baja | B12-B14 | B24 cierre (rango arrastrado) | Sin evidencia documental individual. | Solo aparecen como rango en cierres B18-B24. | sin destino | Recuperar cierres antiguos |
| DC-022 | cerrada | media | B15 | B15.8 (test_candidate_service.py) | CandidateService sin tests unitarios. | `tests/application/test_candidate_service.py` — test implementado en B15.8. | cerrada | — |
| DC-023 | ambigua | baja | B15 | B24 cierre (rango arrastrado) | Sin evidencia documental individual. | Aparece en rango entre DC-022 y DC-024 (ambas cerradas). | sin destino | Recuperar cierre original |
| DC-024 | cerrada | media | B15 | B15.8 (test_orchestrator_service.py) | OrchestratorService sin tests unitarios. | `tests/application/test_orchestrator_service.py` — test implementado en B15.8-T02. | cerrada | — |
| DC-025 | duplicada | ver notas | B16 | HANDOFF.md + B17 cierre | **Dos significados:** (1) HANDOFF: "AnalysisService sin tests unitarios" — Media-baja. (2) B17 cierre: "import review un-reject no implementado" — Baja. | HANDOFF.md línea 59 vs B17 cierre línea 230. La versión B17 es la autoritativa por ser más reciente. El significado HANDOFF queda sin ID. | B17 significado: B26+ | HANDOFF: crear DC-045 para "AnalysisService sin tests" |
| DC-026 | abierta | baja | B17 | B17 cierre | `import review edit` no implementado. | B17 cierre línea 231. | B26+ | — |
| DC-027 | abierta | baja | B17 | B17 cierre | `import review merge` no implementado. Estado FUSIONADO existe en enum pero sin operación. | B17 cierre línea 232. | B26+ | — |
| DC-028 | abierta | baja | B17 | B17 cierre | PDFExtractor requiere `pip install pymupdf` — no incluido en dependencias. | B17 cierre línea 233. CI hace skip condicional. | B26+ | — |
| DC-029 | cerrada | media | B17 | B17.1 (cierre B17 §6.1) | `reject_import_candidate` no idempotente: permite rechazar candidatos ya aceptados sin guarda de estado previo. | B17 cierre líneas 200-202, 234. Cerrada en B17.1. | cerrada | — |
| DC-030 | cerrada | baja | B17 | B17.1 (cierre B17 §6.2) | `_save()` en ImportService es código muerto — definido pero nunca invocado. | B17 cierre líneas 204-206, 235. Cerrada en B17.1. | cerrada | — |
| DC-031 | cerrada | media | B17 | B17.1 (cierre B17 §6.3) | `proposed_relations` se pierde al aceptar — Candidate no tiene ese campo. | B17 cierre líneas 208-210, 236. Cerrada en B17.1. | cerrada | — |
| DC-032 | cerrada | media | B17 | B17.1 (cierre B17 §6.5) | Sin test de persistencia real de `import_baskets` (save/load roundtrip). | B17 cierre líneas 216-218, 237. Cerrada en B17.1. | cerrada | — |
| DC-033 | abierta | baja | B18 | B24 cierre | `get_ordered_events` no maneja `partial_order` real ni ciclos; usa orden simple por `absolute_date`. | B18 cierre línea 79. | B29 | — |
| DC-034 | abierta | baja | B18 | B24 cierre | `TimelineEvent` sin relación automática con `NarrativeEntity(EVENTO)`; `entity_id` es manual. | B18 cierre línea 80. | B25+ | — |
| DC-035 | abierta | baja | B19 | B24 cierre | IA writing usa provider simulado; falta integración con proveedor IA real y validación de outputs writing. | B19 cierre línea 77. | B27 | — |
| DC-036 | abierta | baja | B19 | B24 cierre | `get_tree` no escala para >1000 unidades (recursivo). | B19 cierre línea 78. | B29 | — |
| DC-037 | abierta | baja | B20 | B24 cierre | CampaignService sin integración con HistoryService formal (usa campaign.history textual). | B20 cierre línea 87. | B25 | — |
| DC-038 | abierta | baja | B21 | B24 cierre | SecretsService sin integración con HistoryService. | B21 cierre línea 87. | B25 | — |
| DC-039 | abierta | baja | B21 | B24 cierre | KnowledgeRelationType no integrado con RelationType core (enum propio, sin migración de relaciones existentes). | B21 cierre línea 88. | B25 | — |
| DC-040 | abierta | baja | B21 | B24 cierre | CLI tests de secrets/clues tienen 5 flakes por subprocess en suite non-UI; core y arquitectura pasan. | B21 cierre línea 89. | hardening | — |
| DC-041 | abierta | baja | B22 | B24 cierre | FactionService sin integración con HistoryService formal. | B22 cierre línea 84. | B25 | — |
| DC-042 | abierta | baja | B23 | B24 cierre | SessionService sin integración con HistoryService formal. | B23 cierre línea 79. | B25 | — |
| DC-043 | abierta | baja | B24 | B24 cierre | LiveModeService sin integración con HistoryService formal. | B24 cierre línea 84. | B25 | — |
| DC-044 | abierta | baja | B24 | B24 cierre | `improvise` usa OrchestratorService con fallback determinista; sin IA real. | B24 cierre línea 85. | B27 | — |

---

## 3. DC abiertas por categoría

### HistoryService / trazabilidad (6 DC)
**Patrón:** 6 servicios sin integración con HistoryService formal. Todos usan historia textual o metadata.
| ID | Servicio afectado | Destino |
|----|-------------------|---------|
| DC-037 | CampaignService | B25 |
| DC-038 | SecretsService | B25 |
| DC-041 | FactionService | B25 |
| DC-042 | SessionService | B25 |
| DC-043 | LiveModeService | B25 |
| DC-039 | KnowledgeRelationType vs RelationType | B25 |

### Rendimiento / escalabilidad (2 DC)
| ID | Descripción | Destino |
|----|-------------|---------|
| DC-033 | get_ordered_events sin partial_order real | B29 |
| DC-036 | get_tree recursivo no escala >1000 | B29 |

### CLI / JSON / flakes (1 DC)
| ID | Descripción | Destino |
|----|-------------|---------|
| DC-040 | 5 flakes subprocess en secrets/clues | hardening |

### IA / provider simulado (2 DC)
| ID | Descripción | Destino |
|----|-------------|---------|
| DC-035 | IA writing con provider simulado | B27 |
| DC-044 | improvise con fallback determinista | B27 |

### Importación documental (3 DC)
| ID | Descripción | Destino |
|----|-------------|---------|
| DC-026 | import review edit no implementado | B26+ |
| DC-027 | import review merge no implementado | B26+ |
| DC-028 | PDFExtractor requiere pymupdf | B26+ |

### Modelos especializados ↔ NarrativeEntity (1 DC)
| ID | Descripción | Destino |
|----|-------------|---------|
| DC-034 | TimelineEvent sin sync con NarrativeEntity(EVENTO) | B25+ |

### Sin evidencia documental (17 DC)
| ID | Estado |
|----|--------|
| DC-001 — DC-007, DC-010 — DC-015, DC-017 — DC-021, DC-023 | ambigua |

---

## 4. DC cerradas o absorbidas

| ID | Estado final | Cerrada/absorbida en | Evidencia | Nota |
|----|--------------|----------------------|-----------|------|
| DC-008 | cerrada | B05 | Prompt del usuario | Sin cierre documental |
| DC-009 | cerrada | B06 | `tests/qa/test_dc009_coverage.py` | Test implementado en B06-T03 |
| DC-016 | absorbida | B12 | Prompt del usuario | Sin cierre documental |
| DC-022 | cerrada | B15.8 | `tests/application/test_candidate_service.py` | CandidateService tests |
| DC-024 | cerrada | B15.8 | `tests/application/test_orchestrator_service.py` | OrchestratorService tests |
| DC-029 | cerrada | B17.1 | B17 cierre §6.1 | reject_import_candidate idempotencia |
| DC-030 | cerrada | B17.1 | B17 cierre §6.2 | _save() código muerto |
| DC-031 | cerrada | B17.1 | B17 cierre §6.3 | proposed_relations pérdida |
| DC-032 | cerrada | B17.1 | B17 cierre §6.5 | test persistencia import_baskets |

---

## 5. IDs duplicados o ambiguos

### Duplicidad HANDOFF.md ↔ B17 cierre (5 IDs conflictivos)

HANDOFF.md (líneas 59-63) usa DC-025 a DC-032 con significados distintos a los del cierre B17. El cierre B17 es **posterior y autoritativo** — fue escrito durante el cierre real del bloque, mientras HANDOFF.md es un resumen heredado.

| ID conflictivo | Significado HANDOFF (obsoleto) | Significado B17 (autoritativo) | Decisión | Nuevo ID |
|----------------|-------------------------------|-------------------------------|----------|----------|
| DC-025 | AnalysisService sin tests unitarios (Media-baja) | import review un-reject no implementado (Baja) | Mantener B17. Crear DC-045 para HANDOFF. | DC-045 |
| DC-029 | PDFExtractor solo con pymupdf; sin fallback (Baja) | reject_import_candidate no idempotente (Media, cerrada) | Mantener B17 (ya cerrada). HANDOFF cubierto por DC-028. | — |
| DC-030 | partial_import sin CLI completa (Baja) | _save() código muerto (Baja, cerrada) | Mantener B17 (ya cerrada). HANDOFF significado sin cubrir. | DC-046 |
| DC-031 | Basket.metadata no incluye raw_text (Baja) | proposed_relations se pierde al aceptar (Media, cerrada) | Mantener B17 (ya cerrada). HANDOFF absorbido sin reemplazo. | — |
| DC-032 | ImportService sin tests de PDF (Baja) | sin test de persistencia import_baskets (Media, cerrada) | Mantener B17 (ya cerrada). HANDOFF absorbido sin reemplazo. | — |

### IDs propuestos para significados HANDOFF huérfanos

| Nuevo ID | Descripción | Gravedad | Destino |
|----------|-------------|----------|---------|
| DC-045 | AnalysisService sin tests unitarios dedicados | Media | B29 |
| DC-046 | partial_import sin CLI completa | Baja | B26+ |

---

## 6. Bloques recomendados para resolver deuda

### B25 — HistoryService transversal + post-sesión (7 DC ✅ asignadas → B25-T00)
Agrupadas en **B25-T00** — HistoryService unificado + KnowledgeRelationType → RelationType + TimelineEvent sync.
- DC-034: TimelineEvent sync con NarrativeEntity(EVENTO)
- DC-037: CampaignService → HistoryService
- DC-038: SecretsService → HistoryService
- DC-039: KnowledgeRelationType → RelationType core
- DC-041: FactionService → HistoryService
- DC-042: SessionService → HistoryService
- DC-043: LiveModeService → HistoryService

### hardening — Consolidación pre-B26 (2 DC)
- T01: CLI flakes secrets/clues (DC-040)
- T02: Normalización documental DC + HANDOFF sincronizado

### B26 — Importación documental avanzada (4 DC)
- DC-026: import review edit
- DC-027: import review merge
- DC-028: pymupdf en dependencias
- DC-046: partial_import CLI completa

### B27 — IA avanzada (2 DC)
- DC-035: proveedor IA real para writing
- DC-044: proveedor IA real para improvise

### B29 — Rendimiento y migraciones (3 DC)
- DC-033: partial_order real en timeline
- DC-036: get_tree escalable
- DC-045: AnalysisService tests

---

## 7. Recomendación final

```text
Resolver antes de B25 (7 DC):
  DC-037, DC-038, DC-039, DC-041, DC-042, DC-043, DC-034
  → HistoryService unificado + KnowledgeRelationType integrado
  → Riesgo: sin HistoryService, B25 post-sesión no tiene dónde registrar cambios aceptados

Puede esperar a B26 (4 DC):
  DC-026, DC-027, DC-028, DC-046 → importación avanzada

Puede esperar a B27 (2 DC):
  DC-035, DC-044 → IA real

Puede esperar a B29 (3 DC):
  DC-033, DC-036, DC-045 → rendimiento

Consolidación documental inmediata:
  DC-001..DC-024: marcar como "sin evidencia — descartar o recuperar cierres originales"
  HANDOFF.md: actualizar tabla de deuda con IDs autoritativos (B17+)
  DC-040: documentar y posponer a hardening
```
