# B39-T00 — Inventario de datos del proyecto

**Fecha:** 2026-06-05
**Bloque:** B39
**Autor:** ui-agent + architecture-agent

## Resumen

El modelo de dominio tiene 5 objetos centrales con ~74 campos totales.
De esos, ~30 son visibles en UI normal, ~12 en modo avanzado, y ~32 son internos.

---

## 1. NarrativeEntity (20 campos)

Archivo: `packages/domain/entity.py`
Clase: `NarrativeEntity`
Uso UI: `hosts/DesktopHostPySide/widgets/node_detail_panel.py`

| # | Campo | Tipo | Visible UI normal | Visible avanzado | Persistido | Necesario | Decisión |
|---|-------|------|:-:|:-:|:-:|:-:|----------|
| 1 | `id` | `str` (UUID) | No | No | Sí | Sí (interno) | KEEP_INTERNAL |
| 2 | `name` | `str` | **Sí** | Sí | Sí | Sí | KEEP_VISIBLE → **nombre de hoja/rama** |
| 3 | `aliases` | `list[str]` | No | No | Sí | Opcional | KEEP_INTERNAL |
| 4 | `entity_type` | `EntityType` (enum 21 vals) | **Sí** (combo) | Sí | Sí | Sí | KEEP_VISIBLE → **tipo de hoja/rama** |
| 5 | `brief_description` | `str` | **Sí** (QTextEdit) | Sí | Sí | Sí | KEEP_VISIBLE → **descripción breve** |
| 6 | `extended_description` | `str` | **Sí** (QTextEdit "Cuerpo") | Sí | Sí | Sí | KEEP_VISIBLE → **cuerpo** |
| 7 | `canon_state` | `CanonState` (13 vals) | **Sí** (simplificado: Borrador/Canon) | Sí | Sí | Sí | KEEP_VISIBLE (simplificado) |
| 8 | `visibility_state` | `VisibilityState` (14 vals) | No | **Sí** (avanzado) | Sí | Interno | HIDE_UI → solo avanzado |
| 9 | `certainty_level` | `CertaintyLevel` (5 vals) | No | No | Sí | Interno | KEEP_INTERNAL |
| 10 | `tags` | `list[str]` | No | No | Sí | Opcional | KEEP_INTERNAL |
| 11 | `domain` | `str` | No | No | Sí | Interno | KEEP_INTERNAL |
| 12 | `layers` | `list[str]` | No | No | Sí | Legacy | LEGACY (reemplazado por `layer_ids`) |
| 13 | `origin` | `str` | No | No | Sí | Interno | KEEP_INTERNAL |
| 14 | `domain_ids` | `list[str]` | No | No | Sí | Interno | KEEP_INTERNAL |
| 15 | `layer_ids` | `list[str]` | **Sí** (combo "Capa") | Sí | Sí | Sí | KEEP_VISIBLE → **anillo** |
| 16 | `created_at` | `datetime` | No | No | Sí | Interno | KEEP_INTERNAL |
| 17 | `updated_at` | `datetime` | No | No | Sí | Interno | KEEP_INTERNAL |
| 18 | `private_notes` | `str` | No | **Sí** (avanzado) | Sí | Opcional | HIDE_UI → solo avanzado |
| 19 | `exportable_notes` | `str` | No | **Sí** (avanzado) | Sí | Opcional | HIDE_UI → solo avanzado |
| 20 | `narrative_importance` | `NarrativeImportance` (5 vals) | No | No | Sí | Interno | KEEP_INTERNAL |
| 21 | `development_level` | `DevelopmentLevel` (5 vals) | No | No | Sí | Interno | KEEP_INTERNAL |
| 22 | `custom_metadata` | `dict[str, Any]` | No | No | Sí | Interno | KEEP_INTERNAL |
| 23 | `custom_type_id` | `str \| None` | No | No | Sí | Opcional | KEEP_INTERNAL |
| 24 | `custom_fields` | `list[Any]` | No | No | Sí | Opcional | KEEP_INTERNAL |

**Total NarrativeEntity:** 24 campos
- **KEEP_VISIBLE (modo normal):** 7 (name, entity_type, brief_description, extended_description, canon_state, layer_ids, + contexto relacional)
- **HIDE_UI (solo avanzado):** 3 (visibility_state, private_notes, exportable_notes)
- **KEEP_INTERNAL:** 12 (id, aliases, certainty_level, tags, domain, origin, domain_ids, created_at, updated_at, narrative_importance, development_level, custom_metadata)
- **LEGACY:** 1 (layers → reemplazado por layer_ids)
- **KEEP_INTERNAL:** 2 (custom_type_id, custom_fields)

---

## 2. EntityType (enum, 21 valores)

Archivo: `packages/domain/entity.py`

| Valor | Uso en UX | Es hoja o rama? | Decisión |
|-------|-----------|:---:|----------|
| `PERSONAJE` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `LOCALIZACION` | Combo tipo | **Hoja** (o Rama si es compleja) | KEEP_VISIBLE |
| `FACCION` | Combo tipo | **Rama** por defecto | MIGRATE_TO_BRANCH |
| `CULTURA` | Combo tipo | **Rama** por defecto | MIGRATE_TO_BRANCH |
| `OBJETO` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `EVENTO` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `ESCENA` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `SESION` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `CONFLICTO` | Combo tipo | **Hoja** o **Rama** según alcance | KEEP_VISIBLE |
| `SECRETO` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `PISTA` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `REGLA_DEL_MUNDO` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `TECNOLOGIA` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `SISTEMA_MAGICO` | Combo tipo | **Rama** por defecto | MIGRATE_TO_BRANCH |
| `RELIGION` | Combo tipo | **Rama** por defecto | MIGRATE_TO_BRANCH |
| `IDIOMA` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `INSTITUCION` | Combo tipo | **Rama** por defecto | MIGRATE_TO_BRANCH |
| `CRIATURA` | Combo tipo | **Hoja** | KEEP_VISIBLE |
| `TRAMA` | Combo tipo | **Rama** por defecto | MIGRATE_TO_BRANCH |
| `CONTENEDOR` | Combo tipo | **Rama** (siempre) | MIGRATE_TO_BRANCH |
| `NOTA` | Combo tipo | **Hoja** | KEEP_VISIBLE |

**Migración UX propuesta:**
- 7 tipos se convierten en Rama por defecto: FACCION, CULTURA, SISTEMA_MAGICO, RELIGION, INSTITUCION, TRAMA, CONTENEDOR
- 14 tipos permanecen como Hoja por defecto: PERSONAJE, LOCALIZACION, OBJETO, EVENTO, ESCENA, SESION, CONFLICTO, SECRETO, PISTA, REGLA_DEL_MUNDO, TECNOLOGIA, IDIOMA, CRIATURA, NOTA
- LOCALIZACION puede ser Hoja o Rama según complejidad (acción de conversión disponible)

---

## 3. NarrativeRelation (17+ campos)

Archivo: `packages/domain/relation.py`
Uso UI: `hosts/DesktopHostPySide/widgets/relation_detail_panel.py`

| # | Campo | Tipo | Visible UI | Persistido | Necesario | Decisión |
|---|-------|------|:-:|:-:|:-:|----------|
| 1 | `id` | `str` (UUID) | No | Sí | Interno | KEEP_INTERNAL |
| 2 | `source_id` | `str` | **Sí** (nombre origen) | Sí | Sí | KEEP_VISIBLE → **origen** |
| 3 | `target_id` | `str` | **Sí** (nombre destino) | Sí | Sí | KEEP_VISIBLE → **destino** |
| 4 | `relation_type` | `RelationType` (27+ vals) | **Sí** (combo) | Sí | Sí | KEEP_VISIBLE → **tipo** |
| 5 | `direction` | `Direction` (2 vals) | **Sí** | Sí | Sí | KEEP_VISIBLE → **dirección** |
| 6 | `description` | `str` | **Sí** (QTextEdit) | Sí | Sí | KEEP_VISIBLE → **descripción breve** |
| 7 | `intensity` | `IntensityLevel` (6 vals) | No | Sí | Interno | KEEP_INTERNAL |
| 8 | `temporality` | `str` | No | Sí | Opcional | KEEP_INTERNAL |
| 9 | `causality` | `str` | No | Sí | Opcional | KEEP_INTERNAL |
| 10 | `canon_state` | `CanonState` | No | Sí | Interno | KEEP_INTERNAL |
| 11 | `visibility_state` | `VisibilityState` | No | Sí | Interno | KEEP_INTERNAL |
| 12 | `certainty_level` | `CertaintyLevel` | No | Sí | Interno | KEEP_INTERNAL |
| 13 | `source` | `str` | No | Sí | Interno | KEEP_INTERNAL |
| 14 | `created_at` | `datetime` | No | Sí | Interno | KEEP_INTERNAL |
| 15 | `updated_at` | `datetime` | No | Sí | Interno | KEEP_INTERNAL |
| 16 | `validity_conditions` | `list[str]` | No | Sí | Interno | KEEP_INTERNAL |
| 17 | `tags` | `list[str]` | No | Sí | Opcional | KEEP_INTERNAL |
| 18 | `custom_metadata` | `dict[str, Any]` | No | Sí | Interno | KEEP_INTERNAL |
| 19 | `custom_relation_type_id` | `str \| None` | No | Sí | Opcional | KEEP_INTERNAL |
| 20 | `custom_fields` | `list[Any]` | No | Sí | Opcional | KEEP_INTERNAL |
| 21 | `layer_ids` | `list[str]` | **Sí** (si worldbuilding ON) | Sí | Opcional | KEEP_VISIBLE → **anillo** |

**Total NarrativeRelation:** 21 campos
- **KEEP_VISIBLE:** 6 (source_id, target_id, relation_type, direction, description, layer_ids)
- **KEEP_INTERNAL:** 15

---

## 4. WorldLayer / Anillo (7 campos)

Archivo: `packages/domain/world_layer.py`

| # | Campo | Tipo | Visible UI | Persistido | Necesario | Decisión |
|---|-------|------|:-:|:-:|:-:|----------|
| 1 | `id` | `str` | No | Sí | Interno | KEEP_INTERNAL |
| 2 | `name` | `str` | **Sí** | Sí | Sí | KEEP_VISIBLE → **nombre del anillo** |
| 3 | `description` | `str` | **Sí** | Sí | Sí | KEEP_VISIBLE → **descripción** |
| 4 | `order` | `int` | **Sí** (posición) | Sí | Sí | KEEP_VISIBLE → **orden causal** |
| 5 | `is_visible` | `bool` | No | Sí | Interno | KEEP_INTERNAL |
| 6 | `is_default` | `bool` | No | Sí | Interno | KEEP_INTERNAL |
| 7 | `metadata` | `dict[str, str]` | No | Sí | Interno | KEEP_INTERNAL (contiene causal_rank, causal_role, etc.) |

**Total WorldLayer:** 7 campos
- **KEEP_VISIBLE:** 3 (name, description, order)
- **KEEP_INTERNAL:** 4

---

## 5. Candidate (13 campos)

Archivo: `packages/domain/candidate_issue.py`

| # | Campo | Tipo | Visible UI | Persistido | Necesario | Decisión |
|---|-------|------|:-:|:-:|:-:|----------|
| 1 | `id` | `str` | No | Sí | Interno | KEEP_INTERNAL |
| 2 | `title` | `str` | **Sí** (card) | Sí | Sí | KEEP_VISIBLE |
| 3 | `candidate_type` | `CandidateType` (9 vals) | **Sí** (badge) | Sí | Sí | KEEP_VISIBLE |
| 4 | `state` | `CandidateState` (9 vals) | **Sí** (badge) | Sí | Sí | KEEP_VISIBLE |
| 5 | `proposed_data` | `dict[str, Any]` | Parcial | Sí | Sí | KEEP_VISIBLE (campos relevantes) |
| 6 | `source` | `str` | No | Sí | Interno | KEEP_INTERNAL |
| 7 | `confidence` | `float` | **Sí** (badge) | Sí | Opcional | KEEP_VISIBLE |
| 8 | `justification` | `str` | **Sí** (card) | Sí | Sí | KEEP_VISIBLE |
| 9 | `expected_impact` | `str` | **Sí** (card expandible) | Sí | Opcional | KEEP_VISIBLE |
| 10 | `affected_entity_ids` | `list[str]` | No | Sí | Interno | KEEP_INTERNAL |
| 11 | `affected_relation_ids` | `list[str]` | No | Sí | Interno | KEEP_INTERNAL |
| 12 | `created_at` | `datetime` | No | Sí | Interno | KEEP_INTERNAL |
| 13 | `metadata` | `dict[str, Any]` | No | Sí | Interno | KEEP_INTERNAL |

---

## 6. EntityType vs concepto visible

La renombración B39 NO cambia `EntityType` internamente. Cambia cómo se presenta:

| Concepto UX | Tipo interno | `entity_type` en combo |
|-------------|-------------|----------------------|
| **Hoja** | `NarrativeEntity` donde `entity_type != CONTENEDOR` | PERSONAJE, LOCALIZACION, OBJETO, etc. |
| **Rama** | `NarrativeEntity` donde `entity_type == CONTENEDOR` O árbol (TreeMeta) | CONTENEDOR, FACCION, CULTURA, etc. |
| **Anillo** | `WorldLayer` | N/A (no es entity_type) |

**Nota:** Los árboles (`TreeMeta` en `packages/domain/project.py`) son la representación interna de Ramas. Tienen `name`, `description`, `rules`, `open_questions`, `children`.

---

## 7. Campos de ruido identificados (ocultar en modo normal)

Campos que DEBEN estar en modo avanzado o completamente ocultos:

| Campo | Objeto | Estado actual | Acción B39 |
|-------|--------|---------------|------------|
| `private_notes` | Entity | En avanzado | HIDE_UI (ya hecho) |
| `exportable_notes` | Entity | En avanzado | HIDE_UI (ya hecho) |
| `visibility_state` | Entity, Relation | En avanzado | HIDE_UI (ya hecho) |
| `certainty_level` | Entity, Relation | Nunca visible | KEEP_INTERNAL |
| `narrative_importance` | Entity | Nunca visible | KEEP_INTERNAL |
| `development_level` | Entity | Nunca visible | KEEP_INTERNAL |
| `custom_metadata` | Entity, Relation | Nunca visible | KEEP_INTERNAL |
| `custom_fields` | Entity, Relation | Nunca visible | KEEP_INTERNAL |
| `layers` (legacy) | Entity | Nunca visible | LEGACY |
| `tags` | Entity, Relation | Nunca visible en panel | KEEP_INTERNAL |
| `temporality` | Relation | Nunca visible | KEEP_INTERNAL |
| `causality` | Relation | Nunca visible | KEEP_INTERNAL |
| `intensity` | Relation | Nunca visible | KEEP_INTERNAL |
| `validity_conditions` | Relation | Nunca visible | KEEP_INTERNAL |
| `source` | Relation | Nunca visible | KEEP_INTERNAL |

---

## 8. Paneles UI a auditar

| Panel | Archivo | Estado | Decisión |
|-------|---------|--------|----------|
| Node detail | `widgets/node_detail_panel.py` (1135 líneas) | 7 campos visibles + 3 avanzados | Simplificar etiquetas: "Entidad"→"Hoja"/"Rama" |
| Relation detail | `widgets/relation_detail_panel.py` | 6 campos visibles | Mantener, simplificar |
| Tree detail | `widgets/tree_detail_panel.py` | Detalle de rama/árbol | Etiquetar como "Rama" |
| Inspector | `widgets/inspector_panel.py` | Resumen inline | Adaptar vocabulario |
| Coherence | `widgets/coherence_panel.py` | Resultados IA | Mantener |

---

## 9. Prompts IA que usan modelo viejo

| Archivo | Ubicación | Cambio B39 |
|---------|-----------|------------|
| `packages/application/ai_jobs.py` | `COMMAND_BAR_SYSTEM_PROMPT_ES` | Usar hoja/rama/anillo |
| `packages/application/ai_jobs.py` | `classify_intent()` | Detectar "rama" para facción/cultura |
| `packages/application/ai_jobs.py` | `stage_results()` | Crear candidatos tipo hoja/rama |
| `packages/application/ai_jobs.py` | `COMMAND_BAR_SYSTEM_PROMPT_ES` → JSON schema | Usar "leaf" vs "branch" vs "ring" |

---

## 10. Resumen de campos por objeto

| Objeto | Campos totales | Visibles normal | Visibles avanzado | Internos | Legacy |
|--------|:-:|:-:|:-:|:-:|:-:|
| NarrativeEntity | 24 | 7 | 3 | 13 | 1 |
| EntityType (enum) | 21 vals | 21 (combo) | - | - | - |
| NarrativeRelation | 21 | 6 | 0 | 15 | 0 |
| WorldLayer | 7 | 3 | 0 | 4 | 0 |
| Candidate | 13 | 6 | 0 | 7 | 0 |
| **TOTAL** | **~86** | **22** | **3** | **39** | **1** |
