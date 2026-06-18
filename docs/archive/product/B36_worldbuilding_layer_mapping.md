# B36 — Auditoría y reconciliación de capas causales

Fecha: 2026-06-04
Estado: B36-T01 implementado — contrato MVP de metadata causal sobre las capas existentes

## 1. Contexto real del repositorio

B36 no parte de cero. La auditoría del repo muestra infraestructura ya existente:

- `Project.worldbuilding_active: bool` ya existe en `packages/domain/project.py`.
- `Project.world_layers: list[WorldLayer]` ya existe y persiste en el proyecto.
- `packages/domain/world_layer.py` define `WorldLayer` y `default_world_layers()` con 16 capas contractuales previas.
- `NarrativeEntity.layer_ids` ya existe y persiste.
- `NarrativeRelation.layer_ids` ya existe y persiste.
- Los árboles semánticos son entidades `EntityType.CONTENEDOR`, por tanto pueden reutilizar `NarrativeEntity.layer_ids`; no necesitan modelo paralelo.
- `WorldLayerService` ya existe para CRUD/orden/visibilidad de capas.
- Desktop ya propaga `worldbuilding_active` hacia Creación desde Proyecto/Home.
- `tree_detail_panel.py` ya tiene sección “Worldbuilding y canon”.
- B35 ya implementó `NarrativeContextBuilder.build_for_graph_selection()` y debe extenderse, no duplicarse.

Decisión inicial de planificación: B36 debe trabajar sobre `world_layers` existentes y añadir semántica causal, no reemplazar el sistema de capas ni crear un modelo paralelo de worldbuilding.

## 2. Capas existentes en el repo

Fuente: `packages/domain/world_layer.py`, `default_world_layers()`.

| Orden | ID | Nombre |
|---:|---|---|
| 1 | `layer_premisa` | Premisa estética y tonal |
| 2 | `layer_metafisica` | Metafísica y cosmología |
| 3 | `layer_reglas` | Reglas fundamentales |
| 4 | `layer_fisica` | Física y restricciones materiales |
| 5 | `layer_geografia` | Geografía, clima y recursos |
| 6 | `layer_biologia` | Biología, especies y ecologías |
| 7 | `layer_comunidades` | Comunidades, culturas y sociedades |
| 8 | `layer_economia` | Economía, política e instituciones |
| 9 | `layer_lenguaje` | Lenguaje, símbolos y tradición |
| 10 | `layer_religion` | Religión, mito e ideología |
| 11 | `layer_tecnologia` | Tecnología, magia y sistemas de poder |
| 12 | `layer_historia` | Historia y memoria colectiva |
| 13 | `layer_situacion` | Situación actual |
| 14 | `layer_conflictos` | Conflictos activos |
| 15 | `layer_narrativa` | Narrativa, trama y escenas |
| 16 | `layer_campaña` | Campaña, sesiones y consecuencias |

## 3. Capas causales propuestas para B36

Propuesta de producto recibida para “causas mayores → consecuencias inferiores”:

| Rank causal | Capa propuesta |
|---:|---|
| 1 | Metafísica / causas primeras |
| 2 | Leyes fundamentales |
| 3 | Materia y naturaleza |
| 4 | Geografía y recursos |
| 5 | Vida y ecología |
| 6 | Lenguaje y símbolos |
| 7 | Culturas y sociedades |
| 8 | Economía, política e instituciones |
| 9 | Religión, mito e ideología |
| 10 | Historia y memoria |
| 11 | Conflictos activos |
| 12 | Narrativa y tramas |
| 13 | Personajes y facciones |
| 14 | Status quo |

## 4. Mapping entre capas existentes y capas causales

| Capa existente | Mapping causal | Decisión recomendada |
|---|---|---|
| `layer_premisa` — Premisa estética y tonal | No equivale a causa diegética. Es marco creativo/meta. | Mantener como capa meta con `causal_role=meta_context`, fuera del flujo causa→consecuencia salvo prompts creativos. |
| `layer_metafisica` — Metafísica y cosmología | 1. Metafísica / causas primeras | Equivalencia directa. `causal_rank=1`, `causal_role=root_cause`. |
| `layer_reglas` — Reglas fundamentales | 2. Leyes fundamentales | Equivalencia directa. `causal_rank=2`, `causal_role=fundamental_law`. |
| `layer_fisica` — Física y restricciones materiales | 3. Materia y naturaleza | Equivalencia parcial/directa. `causal_rank=3`, alias IA “Materia y naturaleza”. |
| `layer_geografia` — Geografía, clima y recursos | 4. Geografía y recursos | Equivalencia directa. `causal_rank=4`. |
| `layer_biologia` — Biología, especies y ecologías | 5. Vida y ecología | Equivalencia directa. `causal_rank=5`, alias IA “Vida y ecología”. |
| `layer_lenguaje` — Lenguaje, símbolos y tradición | 6. Lenguaje y símbolos | Equivalencia directa, aunque el orden existente la sitúa tras economía. Para causalidad debe tener `causal_rank=6` aunque `order=9`. |
| `layer_comunidades` — Comunidades, culturas y sociedades | 7. Culturas y sociedades | Equivalencia directa. `causal_rank=7`. |
| `layer_economia` — Economía, política e instituciones | 8. Economía, política e instituciones | Equivalencia directa. `causal_rank=8`. |
| `layer_religion` — Religión, mito e ideología | 9. Religión, mito e ideología | Equivalencia directa. `causal_rank=9`. |
| `layer_historia` — Historia y memoria colectiva | 10. Historia y memoria | Equivalencia directa. `causal_rank=10`. |
| `layer_conflictos` — Conflictos activos | 11. Conflictos activos | Equivalencia directa. `causal_rank=11`. |
| `layer_narrativa` — Narrativa, trama y escenas | 12. Narrativa y tramas | Equivalencia directa. `causal_rank=12`. |
| `layer_campaña` — Campaña, sesiones y consecuencias | No equivale a “Personajes y facciones”; tampoco a Status quo. Es capa de ejecución/partida. | Mantener como capa de runtime/campaña con `causal_role=play_consequence`. B36 no debe tocar Sesión. |
| Sin capa existente específica | 13. Personajes y facciones | No crear capa nueva en T00. Recomendación: alias o uso de entidad tipo `PERSONAJE`/`FACCION` dentro de `layer_narrativa`, `layer_conflictos`, `layer_situacion` o futura capa opcional si producto lo aprueba. |
| `layer_situacion` — Situación actual | 14. Status quo | Equivalencia directa. `causal_rank=14`, alias IA “Status quo”. |
| `layer_tecnologia` — Tecnología, magia y sistemas de poder | No aparece separada en las 14 propuestas; se solapa con Reglas, Física, Economía o Cultura según proyecto. | Mantener como capa válida con `causal_rank` configurable recomendado entre 3 y 8 según metadata. Valor por defecto recomendado: `causal_rank=6.5` o `7`, `causal_role=systemic_power`. |

## 5. Decisión recomendada

Mantener las 16 capas existentes y añadir metadata causal en `WorldLayer.metadata`.

No migrar a 14 capas en B36 MVP.

Motivos:

1. Evita romper persistencia existente: proyectos ya guardan `world_layers` y `layer_ids`.
2. Evita modelo paralelo: `WorldLayer` ya representa capas configurables.
3. Respeta contrato previo del repo: las 16 capas son “canonical defaults” del bloque 10.
4. Permite que la IA use una prioridad explicativa distinta del orden visual existente.
5. Permite alias de producto sin renombrar IDs persistidos.
6. Conserva capas útiles no presentes en la propuesta causal: premisa estética, tecnología/magia, campaña.

Metadata propuesta por capa:

```text
metadata["causal_rank"]: string numérico o entero serializado, ejemplo "1", "6.5", "14"
metadata["causal_role"]: rol semántico, ejemplo root_cause, law, material, ecology, culture, status_quo
metadata["causal_aliases"]: alias legibles para IA separados por coma o JSON simple si se decide permitirlo
metadata["causal_parent_layer_ids"]: IDs de capas superiores típicas, si procede
metadata["causal_notes"]: nota breve para prompts IA
```

Nota técnica: `WorldLayer.metadata` está tipado como `dict[str, str]`, por tanto T01 debe decidir si se mantiene como strings o si se amplía a `dict[str, Any]` con revisión de persistencia. Para MVP se recomienda mantener strings y evitar schema bump si es viable.

## 6. Impacto en persistencia

Impacto mínimo recomendado:

- No cambiar `Project.world_layers`.
- No cambiar `NarrativeEntity.layer_ids`.
- No cambiar `NarrativeRelation.layer_ids`.
- No crear colección nueva de capas causales.
- Añadir metadata causal dentro de `WorldLayer.metadata`.
- Si se inicializa metadata causal por defecto, hacerlo de forma tolerante:
  - proyectos nuevos: defaults con metadata causal.
  - proyectos existentes: helper/servicio que complete metadata ausente sin destruir personalizaciones.

Riesgo principal:

- Si se cambia el tipo de `WorldLayer.metadata` de `dict[str, str]` a `dict[str, Any]`, revisar serialización, tests de dominio y migración schema. Para B36 MVP se recomienda no hacerlo salvo necesidad real.

## 7. Impacto en IA

B36 debe extender contexto y prompts existentes, no crear un pipeline paralelo.

Uso recomendado:

- En prompts, ordenar por `causal_rank` cuando `project.worldbuilding_active=True`.
- Incluir para cada elemento seleccionado:
  - `layer_ids`.
  - nombre de capa.
  - `causal_rank`.
  - `causal_role`.
  - alias/nota causal.
- Para expansión descendente:
  - elemento origen.
  - capa origen.
  - capa destino.
  - causas superiores relevantes.
  - árboles ancestro y reglas internas B34.
  - configuración creativa del proyecto.
- Para explicación ascendente:
  - elemento inferior.
  - capas superiores candidatas.
  - relaciones causales existentes.
  - restricciones de canon/visibilidad.

Regla obligatoria:

- La IA solo devuelve sugerencias/candidatos/parches revisables. No canoniza nodos, árboles ni relaciones sin aceptación explícita.

## 8. Impacto en UI

B36 debe reutilizar la UI existente:

- Mostrar Vista “Capas” solo si `worldbuilding_active=True`.
- Usar `project.world_layers` visibles y ordenadas por metadata causal o `order` como fallback.
- Panel de entidad: selector de capa legible solo si `worldbuilding_active=True`.
- Panel de árbol: mismo selector porque el árbol es `NarrativeEntity(EntityType.CONTENEDOR)`.
- Ocultar controles de capa si `worldbuilding_active=False`.
- No mostrar IDs/JSON/tablas técnicas en modo normal.
- No rediseñar árboles ni resolver DC-034-04 salvo bug bloqueante.

Estado auditado:

- Creación tiene chips de capas y tarjeta “Capas” condicionada por worldbuilding en una zona de workspace.
- `CreationWorkspace.set_worldbuilding_active()` actualmente no parece activar una vista por capas real; T02 debe completar este gap.
- `node_detail_panel.py` y `relation_detail_panel.py` ya exponen `layer_ids` en payload técnico, pero T03 debe convertirlo en selector narrativo visible solo con Worldbuilding ON.
- `tree_detail_panel.py` ya tiene sección “Worldbuilding y canon”; T03 debe reutilizarla.

## 9. Impacto en relaciones causales

Estado real:

- `RelationType.DERIVA_DE` existe.
- `RelationType.CONTRADICE` existe.
- `RelationType.CAUSO` y `RelationType.FUE_CAUSADO_POR` existen.
- `RelationType.DEPENDE_DE` existe.
- No se ha confirmado que existan `condiciona`, `explica` ni `produce_consecuencia_en` como enum directo.

Recomendación:

- T04 debe auditar si conviene añadir nuevos `RelationType` o usar `custom_relation_types`/metadata sin romper contratos.
- Si se añaden enums, verificar schema/tests/CLI/UI y evitar dispatch faltantes.
- Marcar relaciones causales con `custom_metadata["causal_relation"] = "true"` o campo equivalente si no se introduce modelo nuevo.
- No confundir relaciones causales con `CONTIENE`/`PERTENECE_A` de árboles.

## 10. Recomendación final

B36 debe abrirse como bloque incremental sobre infraestructura existente:

1. T00 documenta reconciliación y fija decisión: mantener 16 capas, añadir metadata causal.
2. T01 formaliza contrato causal sobre `WorldLayer.metadata` y `layer_ids` existentes.
3. T02 implementa vista de Creación por bandas/capas usando `world_layers`.
4. T03 añade asignación legible de capa en paneles de entidad/árbol.
5. T04 formaliza relaciones causales sin mezclar pertenencia estructural.
6. T05/T06 añaden IA descendente/ascendente como sugerencias/candidatos.
7. T07 extiende B35 ContextBuilder/coherencia con capas superiores.
8. T08 valida smoke, persistencia y Windows.

La ruta recomendada conserva compatibilidad, evita deuda estructural y da a la IA una jerarquía explicativa sin reescribir el modelo de mundo existente.

## 11. B36-T01 — Contrato causal implementado

B36-T01 materializa esta decisión con un contrato mínimo incremental:

- `WorldLayer.metadata` conserva los campos causales como strings serializables.
- `packages/application/world_layer_causal.py` encapsula lectura, escritura, ordenación y validación.
- UI e IA no deben acceder directamente a `metadata["causal_*"]`.
- `default_world_layers()` mantiene las 16 capas existentes y añade metadata causal seed.
- `NarrativeContextBuilder` consume el helper y expone `world_layers[].causal` sin metadata cruda.
- No hay schema bump ni modelo paralelo.

Contrato técnico detallado: `docs/contracts/b36-causal-layer-contract.md`.
