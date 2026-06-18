# B41 — Hitos causales y memoria histórica del mundo

Ticket: B41-T00 — Auditoría y diseño
Estado: aprobado, implementado y cerrado documentalmente. Ver `docs/cierres/bloque-41-cierre.md`.

## 1. Objetivo del bloque

B41 introduce una memoria histórica/causal del mundo para explicar el status quo desde acontecimientos previos.

La unidad visible nueva será el **Hito**:

- Un acontecimiento histórico o causal relevante.
- Puede explicar hojas, ramas, relaciones y otros hitos.
- Puede estar situado en un anillo/capa causal B36.
- Puede ser canon, hipótesis o candidato pendiente.
- No sustituye a Hoja/Rama/Anillo/Relación.
- No se canoniza automáticamente si lo propone la IA.

Objetivo operativo:

```text
causas primeras / capas superiores
        ↓
hitos históricos y causales
        ↓
relaciones, culturas, conflictos, facciones, personajes, status quo
```

## 2. Auditoría de infraestructura existente

### 2.1 Project y persistencia

`packages/domain/project.py` ya tiene colecciones persistentes relevantes:

- `entities`: hojas y ramas visibles.
- `relations`: relaciones entre entidades.
- `sources`: fuentes trazables.
- `history`: auditoría de mutaciones del proyecto.
- `issues`: incidencias estructuradas.
- `timeline_events`: eventos temporales existentes.
- `candidates`: propuestas revisables.
- `world_layers`: anillos/capas causales B36.
- `worldbuilding_active`: activa flujo worldbuilding.

`Project.to_dict()` persiste `timeline_events`, `candidates`, `world_layers` y `worldbuilding_active`.
`Project.from_dict()` los recarga.

`packages/persistence/schema.py` valida que `timeline_events` sea colección JSON array, pero no valida aún una colección `milestones`.

Implicación:

- Si B41 crea una colección nueva `causal_milestones`, debe añadirse a `Project`, `to_dict`, `from_dict`, migración/schema y tests de persistencia.
- Si B41 reutiliza `timeline_events`, evita migración de colección, pero mezcla semánticas temporales con hitos causales/worldbuilding.

### 2.2 TimelineEvent existente

`packages/domain/temporal_models.py` define `TimelineEvent` con campos:

- `id`, `name`, `description`.
- `entity_id`.
- `temporality` (`EventTemporality`).
- `domain_ids`, `layer_ids`.
- `participant_ids`, `location_id`.
- `cause_ids`, `consequence_ids`.
- `source_ids`.
- `canon_state`, `visibility_state`.
- `session_ids`, `faction_ids`, `secret_ids`, `clue_ids`.
- `metadata`, `created_at`, `updated_at`.

`packages/application/timeline_service.py` ya implementa:

- `create_event()`.
- `get_event()`.
- `list_events()` con filtros por dominio, capa, entidad y canon.
- `get_ordered_events()`.
- `update_event()`.
- `add_participant()`.
- `add_location()`.
- `add_cause()` / `add_consequence()` entre eventos.
- `detect_temporal_inconsistencies()`.

Fortalezas para B41:

- Tiene temporalidad rica.
- Tiene `cause_ids` / `consequence_ids`.
- Tiene `layer_ids`.
- Ya persiste en proyecto.
- Ya soporta referencias a fuentes.

Limitaciones para B41:

- Sus causas/consecuencias solo apuntan a otros `TimelineEvent`, no a hojas/ramas/relaciones.
- `entity_id` singular no basta para hitos que afecten muchas hojas/ramas.
- No distingue hito histórico de evento narrativo/session/temporal genérico.
- No representa directamente “este hito causó esta relación”.
- No tiene estado específico candidato/hipótesis/archivado para memoria histórica; `canon_state` existe, pero no expresa bien hipótesis causal.
- No expone una UX de memoria histórica ni aceptación de hitos IA.

Conclusión de auditoría:

`TimelineEvent` es reutilizable como base temporal o como compatibilidad, pero no debe ser el único modelo de Hito si B41 quiere cumplir la ontología visible Hoja/Rama/Anillo/Relación/Hito.

### 2.3 Source / HistoryEntry / HistoryService

`packages/domain/source_history.py` contiene:

- `Source`: origen trazable de contenido.
- `HistoryEntry`: auditoría de mutaciones del proyecto.
- `HistoryEventType`: creación/edición/canon/visibilidad/relación/sugerencia/importación, etc.

`packages/application/history_service.py` usa `Project.history` como fuente única y `history_entries` como alias. Está orientado a auditoría de cambios, no a historia diegética del mundo.

Conclusión:

- `HistoryEntry` NO debe ser Hito.
- `HistoryService` se reutiliza para registrar aceptación/edición/canonización de hitos.
- La “memoria histórica del mundo” no debe mezclarse con la auditoría técnica del proyecto.

### 2.4 Candidate / CandidateService

`packages/domain/candidate_issue.py` define `Candidate` con:

- `candidate_type` enum: entidad, relación, fuente, cambio, fusión, corrección, incidencia, fragmento, sugerencia IA, propuesta post sesión.
- `state`: pendiente, aceptado, rechazado, editado_aceptado, fusionado, pospuesto, archivado, requiere_revision, parcialmente_aceptado.
- `proposed_data`: dict libre.
- `affected_entity_ids`, `affected_relation_ids`.
- `source`, `confidence`, `justification`, `expected_impact`, `possible_contradictions`, metadata.

`packages/application/candidate_service.py` ya permite crear/listar/aceptar/rechazar candidatos. Actualmente solo canoniza estructuralmente `CandidateType.ENTIDAD` y `CandidateType.RELACION`; otros tipos se marcan aceptados sin crear estructura.

Conclusión:

- Para B41, candidatos IA de hitos deben usar Candidate como bandeja de revisión.
- Hace falta añadir soporte explícito de `CandidateType.HITO` o usar `SUGERENCIA_IA` con `proposed_data.kind = "causal_milestone"` como MVP.
- Recomendación: para MVP B41, usar `SUGERENCIA_IA` + `kind=causal_milestone` hasta implementar `MilestoneService.accept_candidate()`. Evita romper enum y permite revisar sin canon automático.
- En T02/T03, cuando exista servicio de hitos, se puede añadir `CandidateType.HITO` si los tests/migración lo justifican.

### 2.5 Relaciones causales

`packages/domain/relation.py` ya incluye tipos causales:

- `CAUSO` / `FUE_CAUSADO_POR`.
- `DERIVA_DE`.
- `CONDICIONA`.
- `EXPLICA`.
- `CONTRADICE`.
- `PRODUCE_CONSECUENCIA_EN`.

`NarrativeRelation` enlaza solo entidades (`source_id`, `target_id`). También tiene:

- `causality` textual.
- `temporality` textual.
- `layer_ids`.
- `custom_metadata`.

`RelationService` valida que ambos extremos existan como entidades.

Conclusión:

- Las relaciones causales existentes sirven para Hoja↔Hoja, Rama↔Rama y Hoja↔Rama porque ramas son entidades con `display_type="rama"`.
- No sirven directamente para Hito↔Hoja/Rama/Relación si Hito no es entidad.
- B41 debe evitar convertir Hito en Hoja solo para poder usar `NarrativeRelation`; eso rompería la ontología visible.
- La relación “hito causó relación X” debe estar modelada dentro del Hito o en un vínculo específico de hitos, no como `NarrativeRelation` normal entre entidades.

### 2.6 WorldLayer / anillos B36

`packages/domain/world_layer.py` define `WorldLayer` y defaults con metadata causal B36:

- `causal_rank`.
- `causal_role`.
- `causal_parent_layer_ids`.
- aliases causales.

`packages/application/world_layer_service.py` gestiona anillos/capas.

B36 ya añadió las relaciones causales y el contexto causal en `NarrativeContextBuilder`.

Conclusión:

- Hito debe tener `layer_ids` para colocarse en anillos causales.
- Para memoria histórica, el hito puede estar en `layer_historia`, `layer_conflictos`, `layer_situacion`, etc., pero también puede explicar desde capas superiores como `layer_metafisica` o `layer_reglas`.
- No crear otro sistema de capas.

### 2.7 Contexto IA y coherencia B35/B36

`packages/application/narrative_context_builder.py` ya construye `causal_context` cuando `worldbuilding_active=True`:

- `causal_layers` ordenadas por rango causal.
- `upper_cause_entities`.
- `causal_relations`.
- hint de detección de huérfanos causales.

`packages/application/ai_context_actions.py` ya instruye a coherencia:

- usar `causal_context` si worldbuilding está activo.
- detectar elementos sin causa superior/justificación.
- detectar contradicciones entre capas.

`hosts/DesktopHostPySide/widgets/coherence_panel.py` deja claro que análisis/reparación son review-only y no crean nodos/relaciones automáticamente.

Conclusión:

- B41 no debe reescribir B35.
- Debe ampliar `NarrativeContextBuilder` para incluir hitos relevantes en el contexto de selección.
- Debe ampliar prompts de coherencia para considerar hitos como memoria causal, pero seguir devolviendo informe/candidato, no canon automático.

### 2.8 Command bar jobs B38/B40

`packages/application/ai_jobs.py` ya tiene:

- `AIJobType.EXPAND_WORLDBUILDING`.
- `AIJobType.EXPLAIN_FROM_CAUSES`.
- `AIJobType.ANALYZE_COHERENCE`.
- stageado de hojas, ramas, relaciones y sugerencias en candidatos.
- regla explícita: no canon automático.
- contexto creativo B40 y worldbuilding activo.

Limitación:

- El JSON aceptado por command bar no incluye `hitos`/`milestones`.
- `stage_results()` no crea candidatos de hito.

Conclusión:

- B41 debe añadir un output estructurado `hitos`/`milestones` al prompt y stagearlo como candidatos revisables.
- Para MVP, el candidato puede ser `candidate_type="sugerencia_ia"` con `proposed_data.kind="causal_milestone"`.
- La aceptación real de un hito debe esperar a `MilestoneService`.

## 3. Decisión de modelo

### Decisión

Crear un modelo nuevo de dominio: `CausalMilestone` / `HitoCausal`.

No usar `HistoryEntry` como hito.
No convertir hitos en `NarrativeEntity`.
No depender exclusivamente de `TimelineEvent`.

### Justificación

Hito es una unidad ontológica visible distinta:

```text
Hoja      = individuo/cosa singular
Rama      = agrupación/sistema/colectivo
Anillo    = estrato causal/worldbuilding
Relación  = vínculo entre hojas/ramas
Hito      = acontecimiento histórico/causal que explica cambios y status quo
```

`TimelineEvent` cubre temporalidad, pero no cubre suficientemente:

- vínculos con múltiples hojas/ramas.
- vínculos con relaciones causadas.
- estado hipótesis/candidato/canon específico.
- rol causal visible.
- explicación de status quo.
- candidatos IA de hitos.

### Relación con TimelineEvent

Dos opciones compatibles:

1. **MVP recomendado:** `CausalMilestone` incluye una `temporality: EventTemporality` o campos temporales equivalentes, sin crear `TimelineEvent` automáticamente.
2. **Compatibilidad futura:** `CausalMilestone.timeline_event_id: str | None` para enlazar con un evento temporal si el usuario quiere verlo también en línea temporal.

No crear duplicados automáticamente en `timeline_events` durante B41 MVP.

## 4. Modelo mínimo propuesto

Archivo sugerido:

`packages/domain/causal_milestone.py`

Nombre clase:

`CausalMilestone`

Campos mínimos:

```python
id: str
name: str
description: str
milestone_type: CausalMilestoneType
state: CausalMilestoneState
layer_ids: list[str]
temporality: EventTemporality
affected_entity_ids: list[str]
caused_relation_ids: list[str]
causal_parent_milestone_ids: list[str]
causal_child_milestone_ids: list[str]
causal_parent_entity_ids: list[str]
causal_child_entity_ids: list[str]
source_ids: list[str]
canon_state: str
visibility_state: str
confidence: float
justification: str
created_at: str
updated_at: str
metadata: dict[str, Any]
```

Tipos sugeridos:

```text
origen
fundacion
ruptura
guerra
pacto
traicion
descubrimiento
catastrofe
migracion
reforma
revelacion
invencion
colapso
ascenso_poder
caida_poder
mitificacion
memoria_colectiva
otro
```

Estados sugeridos:

```text
candidate      # propuesto, no canon
hypothesis     # hipótesis aceptada como trabajo, no canon duro
canon          # hito canonizado por usuario
rejected       # descartado
archived       # histórico del proyecto, no activo
```

Reglas:

- IA crea `candidate`, nunca `canon`.
- El usuario puede promover candidate/hypothesis a canon.
- Los hitos no son entidades, pero pueden afectar entidades.
- Los hitos pueden explicar relaciones existentes con `caused_relation_ids`.
- Los hitos pueden tener causas superiores en entidades/anillos y en otros hitos.

## 5. Servicio de aplicación propuesto

Archivo sugerido:

`packages/application/causal_milestone_service.py`

Responsabilidades:

- CRUD de hitos en `Project.causal_milestones`.
- Validar referencias a entidades, relaciones, fuentes, capas e hitos.
- Aceptar candidato de hito.
- Rechazar/archivar hito.
- Promover hipótesis/candidate a canon por acción explícita del usuario.
- Consultar hitos por entidad, relación, capa, estado, tipo y subgrafo.
- Detectar huecos causales locales.

Métodos MVP sugeridos:

```python
create_milestone(data) -> Result[CausalMilestone, str]
update_milestone(milestone_id, data) -> Result[CausalMilestone, str]
get_milestone(milestone_id) -> Result[CausalMilestone, str]
list_milestones(filters=None) -> Result[list[CausalMilestone], str]
list_for_selection(entity_ids=None, relation_ids=None) -> Result[list[CausalMilestone], str]
link_parent_milestone(child_id, parent_id) -> Result[CausalMilestone, str]
link_affected_entity(milestone_id, entity_id) -> Result[CausalMilestone, str]
link_caused_relation(milestone_id, relation_id) -> Result[CausalMilestone, str]
promote_to_canon(milestone_id) -> Result[CausalMilestone, str]
archive_milestone(milestone_id) -> Result[CausalMilestone, str]
validate_milestone(milestone) -> list[str]
```

Historia/auditoría:

- Usar `HistoryService.record()` al crear, editar, promover, archivar y aceptar candidatos.
- Si `HistoryEventType` no tiene tipo específico, usar evento genérico compatible y `metadata.object_type="causal_milestone"`.
- No crear segundo sistema de auditoría.

## 6. Persistencia y migración

Añadir a `Project`:

```python
causal_milestones: list[CausalMilestone] = field(default_factory=list)
```

Añadir a `to_dict()`:

```python
"causal_milestones": [m.to_dict() for m in self.causal_milestones]
```

Añadir a `from_dict()`:

```python
causal_milestones=[CausalMilestone.from_dict(m) for m in data.get("causal_milestones", []) if isinstance(m, dict)]
```

Añadir a schema/migración:

- `causal_milestones` default `[]`.
- Validación estructural básica: lista, id único, referencias a ids existentes cuando aplique.
- Backward compatibility: proyectos antiguos sin campo cargan con lista vacía.

No migrar automáticamente `timeline_events` a hitos en MVP.

## 7. Integración con Hoja/Rama/Anillo/Relación

### Hoja/Rama

- Referencia por `affected_entity_ids`, `causal_parent_entity_ids`, `causal_child_entity_ids`.
- Ramas siguen siendo entidades con `display_type="rama"`.
- No crear modelo paralelo para árboles.

### Anillo

- Hito usa `layer_ids` igual que entidades/relaciones.
- La UI puede filtrar hitos por anillo.
- Si `worldbuilding_active=False`, la UX de anillos/hitos causales avanzados debe ocultarse o degradarse a historia simple.

### Relación

- `caused_relation_ids` explica qué relaciones existen por causa de un hito.
- No usar `NarrativeRelation` para enlazar hito↔entidad porque `RelationService` solo admite entidades.
- Sí se pueden crear relaciones causales normales entre hojas/ramas cuando el usuario acepta una consecuencia concreta.

## 8. Integración con B35 coherencia

B41 debe ampliar el análisis de coherencia local:

Entradas adicionales:

- Hitos que afectan entidades seleccionadas.
- Hitos que causan relaciones seleccionadas.
- Hitos padres/causas de esos hitos.
- Hitos en capas superiores relevantes cuando `worldbuilding_active=True`.

Nuevas detecciones locales:

- Elemento seleccionado sin causa superior ni hito justificativo.
- Relación causal fuerte sin hito/fuente/historia que la explique.
- Status quo sin cadena mínima de hitos causales.
- Hito que contradice capa superior o canon duro.
- Hito canon que causa relación inexistente o entidad inexistente.

Regla:

- B35/B41 no hacen análisis global completo.
- Solo selección/subgrafo y vecindario relevante.
- Resultado como informe o candidato revisable; no crear canon.

## 9. Integración con B36 anillos causales

`NarrativeContextBuilder._causal_context()` debe incluir una sección nueva:

```json
"causal_milestones": {
  "relevant": [...],
  "upper_cause_milestones": [...],
  "child_consequence_milestones": [...]
}
```

Orden sugerido:

1. Hitos directamente vinculados a selección.
2. Hitos en capas superiores por `causal_rank`.
3. Hitos padres de hitos relevantes.
4. Hitos que causan relaciones seleccionadas.

No incluir secretos no autorizados. Respetar las mismas reglas de audiencia de `NarrativeContextBuilder`.

## 10. Integración con B38 command bar jobs

Añadir al prompt de command bar output opcional:

```json
"hitos": [
  {
    "name": "...",
    "milestone_type": "fundacion|ruptura|...",
    "description": "...",
    "layer_ids": ["layer_historia"],
    "affected_entity_names": ["..."],
    "caused_relation_names": ["..."],
    "causal_parent_milestone_names": ["..."],
    "justification": "...",
    "confidence": 0.6
  }
]
```

`stage_results()` debe convertir `hitos` en candidatos revisables.

MVP recomendado:

```python
candidate_type = "sugerencia_ia"
proposed_data = {
    "kind": "causal_milestone",
    ...
}
```

Cuando `MilestoneService` exista, se añade aceptación real:

- aceptar candidato → crear `CausalMilestone` en estado `candidate` o `hypothesis`, según acción usuario.
- canonizar → acción explícita separada.

## 11. UX MVP sugerida

No diseñar pantalla enorme en T00/T01. MVP incremental:

1. Panel/lista “Hitos” en Creación solo si Worldbuilding ON o si el usuario activa Historia causal.
2. Cards sin JSON/IDs:
   - nombre
   - tipo
   - estado
   - capa/anillo
   - afecta a
   - explica relaciones
   - causas previas
   - consecuencias
3. Acciones:
   - Crear hito manual.
   - Vincular a selección.
   - Proponer hito con IA.
   - Aceptar/descartar candidato.
   - Promover a canon.
4. En coherencia, mostrar “memoria causal usada” como texto humano.

No hacer en B41:

- timeline visual completo.
- calendario avanzado.
- embeddings/cache.
- importación documental avanzada.
- generación de novela/sesión.
- transformar hitos en nodos de grafo por defecto.

## 12. Plan de tickets recomendado tras T00

### B41-T01 — Modelo `CausalMilestone` y persistencia mínima

- Crear dominio puro.
- Añadir colección en Project.
- Añadir schema/migración.
- Tests de roundtrip.

### B41-T02 — Servicio de hitos

- CRUD.
- Validación de referencias.
- listados por selección/capa/estado.
- historia de auditoría.

### B41-T03 — Candidatos de hitos IA/manual

- Stagear `hitos` de command bar como candidatos.
- Aceptar/rechazar candidatos de hito sin canon automático.
- No modificar entidades/relaciones automáticamente.

### B41-T04 — Contexto IA con memoria histórica

- Ampliar `NarrativeContextBuilder`.
- Prompts de coherencia y command bar con hitos relevantes.

### B41-T05 — UI MVP de hitos

- Cards/lista simple.
- Crear/vincular/promover.
- Ocultar si no corresponde.

### B41-T06 — Coherencia con hitos

- Detectar huecos causales locales.
- Detectar relaciones/status quo sin hito/causa.
- Detectar contradicciones hito↔capa/canon.

### B41-T07 — Smoke end-to-end

- Crear mundo con capas.
- Crear hito fundacional.
- Vincular a cultura/relación/conflicto.
- Analizar coherencia.
- Guardar/cerrar/reabrir.

### B41-T08 — Cierre Windows

- Validación nativa Windows por usuario.
- Cierre técnico con output real.

## 13. Pruebas mínimas por ticket

B41-T01:

- `tests/domain/test_b41_causal_milestone.py`
- `tests/persistence/test_b41_causal_milestones_persistence.py`

B41-T02:

- `tests/application/test_b41_causal_milestone_service.py`

B41-T03/T04:

- `tests/application/test_b41_ai_milestone_candidates.py`
- `tests/application/test_b41_context_includes_milestones.py`

B41-T05:

- `tests/desktop/test_b41_milestone_panel.py`

B41-T06:

- `tests/application/test_b41_coherence_milestones.py`

Actualizar `scripts/run_all_tests.py` con suite `b41` al crear tests.

Validaciones generales:

```text
python -m compileall hosts/DesktopHostPySide packages -q
python -m pytest tests/architecture/ -q
python scripts/run_all_tests.py --suites arch desktop infra sanity b33 b34 b35 b36 b37 b38 b39 b40 b41
```

Nota: según preferencia del usuario, no ejecutar regresión completa salvo petición/validación de cierre; los tests específicos sí deben añadirse a suites cuando se implementen.

## 14. Riesgos y decisiones abiertas

### Riesgo: duplicar TimelineEvent

Mitigación:

- `CausalMilestone` no crea `TimelineEvent` automáticamente.
- Si se requiere timeline visual, enlazar mediante `timeline_event_id` futuro.

### Riesgo: convertir Hito en nodo de grafo y contaminar Hoja/Rama

Mitigación:

- Hito no es `NarrativeEntity`.
- En grafo puede mostrarse como overlay/card opcional, no como Hoja/Rama por defecto.

### Riesgo: IA genere ruido histórico

Mitigación:

- Toda salida IA se stagea como Candidate.
- Aceptar candidato no canoniza automáticamente.
- Promoción a canon es acción explícita.
- Límite de número de hitos sugeridos por prompt/config B40.

### Riesgo: relaciones hito↔entidad sin modelo formal

Mitigación:

- Usar listas de referencias dentro de Hito para MVP.
- No forzar `NarrativeRelation` con endpoints no entidad.
- Si en futuro se necesita grafo heterogéneo, diseñar `CausalLink` separado.

## 15. Decisión final B41-T00

B41 debe implementar Hitos como modelo nuevo `CausalMilestone`, reutilizando:

- `EventTemporality` para temporalidad.
- `Candidate` para revisión de propuestas IA/manuales.
- `HistoryService` para auditoría de aceptación/edición/canonización.
- `WorldLayer` para anillos/capas.
- `NarrativeRelation` existente para relaciones causales entre Hoja/Rama, pero no para enlazar Hito como endpoint.
- `NarrativeContextBuilder` para inyectar memoria histórica en IA/coherencia.

No reutilizar:

- `HistoryEntry` como historia diegética.
- `NarrativeEntity` como Hito.
- `TimelineEvent` como sustituto completo de Hito.

B41 debe avanzar incrementalmente desde modelo/persistencia hacia servicio, candidatos, contexto IA, UI y coherencia.
