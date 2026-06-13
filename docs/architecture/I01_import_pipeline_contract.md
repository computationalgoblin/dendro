# I01 - Contrato de importacion narrativa avanzada

## Objetivo

La importacion documental de Dendro convierte TXT, Markdown y PDF textual en
material revisable para el proyecto narrativo. Puede proponer entidades, ramas,
relaciones, hitos, sugerencias de anillo, aliases, fusiones e incidencias, pero
no modifica canon directamente.

Principio de producto:

```text
Documento importado -> analisis -> candidates -> revision -> aceptacion -> canon
```

La aceptacion final siempre pasa por servicios normales de aplicacion y queda
trazada. La IA, los extractores y la UI de importacion solo producen material de
revision.

## Auditoria previa del repo

I01 parte de una base B17 ya implementada. El contrato no autoriza crear una
pipeline paralela ni sustituir modelos existentes sin migracion explicita.

Componentes existentes:

- `ImportFormat`, `ImportReviewState`, `DocumentSegment`, `ImportCandidate` e
  `ImportBasket` viven en `packages/domain/import_models.py`.
- `ImportService` vive en `packages/application/import_service.py`.
- `Source` se reutiliza con `SourceType.DOCUMENTO_IMPORTADO`.
- `ImportController` expone la capa de aplicacion a Desktop.
- `ImportExportView` muestra bandejas/candidates y oculta datos tecnicos salvo
  modo avanzado.
- `Project.import_baskets` persiste las bandejas de revision.
- `CorpusIndexer` ya indexa importaciones aceptadas por defecto y permite
  incluir importaciones no aceptadas con `include_unaccepted_imports=True`.
- Los tests actuales cubren roundtrip, importacion TXT basica, accept/reject,
  idempotencia de accept y visibilidad conservadora en RAG.

Fortalezas actuales:

- El patron commit-at-end de `ImportService.import_document()` evita mutaciones
  parciales si falla la extraccion.
- Aceptar un `ImportCandidate` crea un `Candidate` B14 en estado pendiente, no
  una entidad ni relacion canonica.
- Rechazar un candidate no crea canon.
- La fuente documental se guarda como `Source`, evitando un modelo de fuente
  paralelo.
- El RAG excluye importaciones pendientes/rechazadas por defecto.

Carencias auditadas:

- `ImportFormat` solo cubre `text_plain` y `pdf`; falta Markdown.
- El chunking actual es por parrafos/paginas, no por unidades narrativas
  estables.
- `DocumentSegment.metadata` puede guardar pagina/extractor, pero no hay
  contrato estable para `chunk_id`, orden, pagina inicial/final, texto normalizado
  o advertencias de extraccion.
- `ImportCandidate.proposed_data` no tiene esquemas por tipo de candidate.
- `SourceReference` no existe como contrato first-class dentro del payload.
- La extraccion de candidates es heuristica y simple; I03 debe sustituirla por
  extraccion IA estructurada sin fallback simulado.
- La fusion/deduplicacion actual marca duplicados y puede crear candidates
  fusionados, pero no modela todavia sugerencias de merge revisables con razon.
- La UI de review es funcional, pero todavia no es un workspace de edicion,
  comparacion y aceptacion por lotes.
- La integracion RAG no diferencia explicitamente `raw_import`, `reviewed` y
  `accepted` como estados de recuperacion.
- El mapeo de edicion heredado usa claves mixtas (`name`, `entity_name`,
  `entity_description`) y debe regularizarse en I03-I05.

## Nombres autoritativos

El bloque de producto puede hablar de `ImportBatch` como concepto funcional de
lote importado. En el repo, el modelo autoritativo existente es `ImportBasket`.

Regla:

- No se crea un `ImportBatch` persistente paralelo mientras `ImportBasket`
  pueda representar el mismo concepto.
- Si en el futuro se renombra `ImportBasket` a `ImportBatch`, debe hacerse con
  migracion, compatibilidad de carga y tests de schema.
- Hasta entonces, `ImportBasket` es el lote revisable de importacion.

## Modelo de documento importado

Un documento importado se representa asi:

- `Source`: origen documental persistido con
  `SourceType.DOCUMENTO_IMPORTADO`.
- `ImportBasket`: bandeja revisable asociada a un `source_id`.
- `DocumentSegment`: chunk extraido del documento.
- `ImportCandidate`: propuesta revisable generada desde uno o varios chunks.

Campos minimos que I02 debe preservar o anadir de forma compatible:

- `ImportBasket.metadata.document_id`
- `ImportBasket.metadata.file_name`
- `ImportBasket.metadata.file_path`
- `ImportBasket.metadata.import_format`
- `ImportBasket.metadata.imported_at`
- `ImportBasket.metadata.extraction_warnings`
- `DocumentSegment.metadata.chunk_id`
- `DocumentSegment.metadata.chunk_order`
- `DocumentSegment.metadata.page_start`
- `DocumentSegment.metadata.page_end`
- `DocumentSegment.metadata.section_path`
- `DocumentSegment.metadata.normalized_text`
- `DocumentSegment.metadata.extraction_method`

Si se anaden campos reales a los dataclasses, deben seguir serializando desde y
hacia los campos actuales para mantener proyectos antiguos.

## SourceReference

`SourceReference` es un value object contractual para trazabilidad fina. Puede
implementarse como dataclass o como diccionario validado dentro de
`ImportCandidate.proposed_data`, pero no sustituye a `Source`.

Campos minimos:

- `source_id`
- `source_name`
- `segment_id`
- `chunk_id`
- `section_path`
- `page_start`
- `page_end`
- `char_start`
- `char_end`
- `quote_excerpt`
- `extraction_method`

Reglas:

- Todo candidate generado desde documentos debe incluir al menos una
  `source_reference`.
- `quote_excerpt` debe ser breve y solo servir para revisar origen, no para
  copiar documentos completos.
- Las referencias sobreviven a edicion, fusion y aceptacion.
- Al crear canon, las referencias se trasladan a fuentes, historial o metadata
  mediante servicios de aplicacion.

## Esquemas de candidates

`ImportCandidate` sigue siendo el wrapper persistente. El tipo narrativo se
define con `candidate_type` y `proposed_data.kind`.

Campos comunes de `proposed_data`:

- `kind`
- `title`
- `summary`
- `body`
- `confidence_reason`
- `source_references`
- `review_notes`
- `suggested_actions`
- `duplicate_candidates`
- `contradiction_candidates`

### EntityCandidate

`kind = "entity"`

Campos especificos:

- `name`
- `entity_type`
- `aliases`
- `brief_description`
- `description`
- `suggested_ring_id`
- `suggested_ring_name`
- `suggested_branch_id`
- `suggested_branch_name`
- `visibility`

### BranchCandidate

`kind = "branch"`

Campos especificos:

- `name`
- `branch_type`
- `parent_branch_id`
- `parent_branch_name`
- `suggested_ring_id`
- `suggested_ring_name`
- `member_entity_names`
- `branch_description`

Una rama aceptada debe crearse como entidad/estructura del core existente, no
como modelo paralelo de rama.

### RelationCandidate

`kind = "relation"`

Campos especificos:

- `source_entity_id`
- `source_entity_name`
- `target_entity_id`
- `target_entity_name`
- `relation_type`
- `description`
- `confidence`
- `directionality`
- `evidence`
- `suggested_missing_entities`

Si el origen o destino no existe, el candidate debe proponer primero entidades o
pedir resolucion en review. No debe inventar IDs canonicos.

### MilestoneCandidate

`kind = "milestone"`

Campos especificos:

- `title`
- `description`
- `linked_entity_ids`
- `linked_entity_names`
- `linked_relation_ids`
- `linked_ring_ids`
- `date_label`
- `structured_date`
- `causal_predecessor_names`
- `causal_successor_names`

La aceptacion debe delegar en el servicio de hitos/cronologia disponible.

### RingSuggestion

`kind = "ring_suggestion"`

Campos especificos:

- `ring_name`
- `ring_order_hint`
- `reason`
- `affected_candidate_ids`
- `candidate_entity_names`

Una sugerencia de anillo no crea anillos automaticamente. Debe presentarse como
decision de review y resolverse con el servicio de anillos/capas.

### MergeSuggestion

`kind = "merge_suggestion"`

Campos especificos:

- `left_ref`
- `right_ref`
- `reason`
- `confidence`
- `fields_to_merge`
- `conflicting_fields`
- `recommended_resolution`

La fusion de candidates no puede borrar evidencias ni referencias. Si hay duda,
se mantiene como sugerencia revisable.

### ImportIssue

`kind = "import_issue"`

Campos especificos:

- `issue_type`
- `severity`
- `message`
- `affected_candidate_ids`
- `affected_source_references`
- `suggested_fix`

`ImportIssue` no autoriza un segundo sistema de incidencias. Cuando sea una
incidencia canonica o de coherencia, debe convertirse mediante el servicio de
issues existente.

## Extraccion IA

I03 debe usar el proveedor IA configurado para extraer candidates estructurados
desde chunks. No hay fallback de IA simulado.

Reglas:

- Si no hay proveedor IA activo, la accion devuelve error explicito o job
  fallido recuperable.
- La segmentacion determinista puede seguir funcionando sin IA.
- La extraccion IA debe devolver JSON validable contra los esquemas de este
  contrato.
- Una respuesta incompleta o invalida se convierte en `ImportIssue` o error de
  job, no en canon.
- La IA nunca recibe permiso para escribir directamente en `Project.entities`,
  `Project.relations`, `Project.causal_milestones` ni estructuras canonicas.
- El timeout de llamadas largas debe respetar el contrato activo de IA/RAG
  vigente para el proyecto.

## Review y aceptacion

Estados autoritativos:

- `pendiente`
- `editado`
- `aceptado`
- `rechazado`
- `fusionado`
- `parcial`

Reglas de review:

- El usuario puede editar el payload antes de aceptar.
- El usuario puede rechazar un candidate sin efectos canonicos.
- El usuario puede aceptar parcialmente campos o relaciones.
- El usuario puede fusionar candidates manteniendo historial y referencias.
- Las acciones por lotes deben mostrar resumen y mantener posibilidad de
  inspeccion individual.

Reglas de aceptacion:

- La UI no escribe directamente en persistencia.
- La aceptacion canonica delega en servicios de aplicacion existentes.
- Entidades y ramas se crean/actualizan mediante servicios de entidad/arbol.
- Relaciones se crean/actualizan mediante servicios de relacion.
- Hitos se crean/actualizan mediante servicios de cronologia.
- Anillos/capas se crean/actualizan mediante servicios de capas/anillos.
- Fuentes e historial se registran mediante los servicios de trazabilidad.

Compatibilidad con B17:

- `ImportService.accept_import_candidate()` puede seguir creando un `Candidate`
  B14 pendiente como paso intermedio.
- Ese paso intermedio no es canon y cumple la regla de no modificacion directa.
- I05 puede ofrecer una experiencia de review que internamente use ese puente o
  que aplique candidates mediante servicios, siempre con aceptacion explicita.

## Integracion con RAG

La importacion documental participa en el RAG con tres estados conceptuales:

- `raw_import`: segmentos o candidates aun no aceptados.
- `reviewed`: material editado, parcial, fusionado o revisado.
- `accepted`: material aceptado y trazado.

Reglas:

- Por defecto, el RAG no recupera `raw_import`.
- `include_unaccepted_imports=True` permite recuperar importaciones no aceptadas
  para tareas de revision, debugging o acciones explicitas de importacion.
- Candidates rechazados quedan fuera salvo modo debug explicito.
- Material aceptado que ya ha creado canon debe recuperarse preferentemente
  desde el canon y conservar referencia al documento como fuente.
- Los prompts de IA deben mostrar al modelo la diferencia entre contexto canonico
  y material importado pendiente.

## UX esperada

La UI principal de importacion debe comportarse como un workspace de review:

- Importar TXT, Markdown y PDF textual.
- Mostrar documento, chunks y candidates sin exponer IDs por defecto.
- Permitir editar candidates con campos comprensibles.
- Mostrar referencias de fuente y extractos cortos.
- Detectar posibles duplicados y fusiones.
- Aceptar, rechazar, fusionar o aceptar parcialmente.
- Tener modo avanzado para JSON, IDs, offsets, paginas y warnings.
- No bloquear la app durante extraccion IA o RAG.

## Persistencia y migracion

Las ampliaciones del bloque I deben ser compatibles con proyectos existentes:

- No se eliminan campos B17.
- Nuevos campos deben tener defaults seguros.
- `from_dict()` debe tolerar datos antiguos.
- `to_dict()` debe preservar metadata desconocida.
- Los tests deben cubrir guardado, cierre y recarga.

## Tests requeridos por bloque

I01:

- Test documental/estatico del contrato.

I02:

- Extraccion TXT, Markdown y PDF textual.
- Chunking narrativo estable.
- Roundtrip de metadata de chunks.

I03:

- Validacion de JSON IA.
- Error explicito sin proveedor IA.
- No fallback simulado.
- Candidates con `source_references`.

I04:

- Duplicados, aliases, merge suggestions y conflictos.
- No perdida de referencias al fusionar.

I05:

- Review workspace con accept/reject/edit/partial/merge.
- Persistencia y recarga de decisiones.
- Canon creado solo mediante servicios.

I06:

- Indexacion RAG separando `raw_import`, `reviewed` y `accepted`.
- Exclusion conservadora por defecto.
- Inclusion explicita con `include_unaccepted_imports=True`.

I07:

- Smoke end-to-end desde documento hasta canon aceptado.
- Regresion de no canon directo.
- Regresion de trazabilidad y recarga.

## Fuera de alcance de I01

- Implementar extractores nuevos.
- Llamar a proveedores IA.
- Crear UI final de review.
- Migrar schema.
- Cambiar comportamiento runtime de importacion.

