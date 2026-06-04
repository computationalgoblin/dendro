# B36 — Contrato de capas causales

Estado: B36-T01 implementado como contrato MVP incremental sobre las capas existentes.

## Decisión de producto

B36 mantiene las 16 capas existentes definidas en `packages/domain/world_layer.py`.
No se migra a las 14 capas propuestas en la ideación inicial y no se crea un modelo paralelo.
Las 14 capas siguen siendo referencia conceptual, no contrato de persistencia.

Infraestructura reutilizada:

- `Project.worldbuilding_active`
- `Project.world_layers`
- `WorldLayer.metadata`
- `NarrativeEntity.layer_ids`
- `NarrativeRelation.layer_ids`
- árboles como `EntityType.CONTENEDOR`

## Contrato causal MVP

La semántica causal se guarda en `WorldLayer.metadata` con valores simples compatibles con la serialización actual:

- `causal_rank`: string con entero; menor número significa causa superior.
- `causal_role`: token compacto de rol causal.
- `causal_aliases`: lista serializada como CSV simple.
- `causal_parent_layer_ids`: lista serializada como CSV simple.
- `causal_notes`: texto libre.

No hay schema bump en B36-T01.

## Única vía de acceso

UI e IA no deben leer ni escribir directamente:

- `WorldLayer.metadata["causal_rank"]`
- `WorldLayer.metadata["causal_role"]`
- `WorldLayer.metadata["causal_aliases"]`
- `WorldLayer.metadata["causal_parent_layer_ids"]`
- `WorldLayer.metadata["causal_notes"]`

La vía autorizada es `packages/application/world_layer_causal.py`:

- `get_causal_rank(layer) -> int | None`
- `set_causal_rank(layer, rank)`
- `get_causal_role(layer) -> str | None`
- `set_causal_role(layer, role)`
- `get_causal_aliases(layer) -> list[str]`
- `set_causal_aliases(layer, aliases)`
- `get_causal_parent_layer_ids(layer) -> list[str]`
- `set_causal_parent_layer_ids(layer, layer_ids)`
- `get_causal_notes(layer) -> str`
- `set_causal_notes(layer, notes)`
- `is_causally_above(layer_a, layer_b)`
- `is_causally_below(layer_a, layer_b)`
- `sort_layers_by_causal_rank(layers)`
- `validate_causal_metadata(layers)`
- `apply_default_causal_metadata(layers, overwrite=False)`
- `causal_layer_summary(layer)`

`NarrativeContextBuilder` consume esta vía y expone un resumen causal estructurado bajo `project.world_layers[].causal`, sin exponer metadata cruda.

## Defaults sobre las 16 capas existentes

`default_world_layers()` inicializa metadata causal para las 16 capas existentes:

| Capa existente | Rank causal | Rol causal |
| --- | ---: | --- |
| Premisa estética y tonal | — | `meta_context` |
| Metafísica y cosmología | 1 | `root_cause` |
| Reglas fundamentales | 2 | `fundamental_law` |
| Física y restricciones materiales | 3 | `material_nature` |
| Geografía, clima y recursos | 4 | `geography_resources` |
| Biología, especies y ecologías | 5 | `life_ecology` |
| Lenguaje, símbolos y tradición | 6 | `language_symbols` |
| Comunidades, culturas y sociedades | 7 | `cultures_societies` |
| Economía, política e instituciones | 8 | `economy_politics_institutions` |
| Religión, mito e ideología | 9 | `religion_myth_ideology` |
| Tecnología, magia y sistemas de poder | 10 | `technology_magic_power_systems` |
| Historia y memoria colectiva | 11 | `history_memory` |
| Conflictos activos | 12 | `active_conflicts` |
| Narrativa, trama y escenas | 13 | `narrative_plots_characters` |
| Situación actual | 14 | `status_quo` |
| Campaña, sesiones y consecuencias | 15 | `play_consequence` |

La premisa estética queda sin `causal_rank` porque es meta-contexto creativo, no causa diegética interna.

## Persistencia

La persistencia sigue usando `WorldLayer.to_dict()` / `WorldLayer.from_dict()` y `Project.to_dict()` / `Project.from_dict()`.
Como los campos causales viven dentro de `metadata`, guardar/cargar conserva el contrato sin migración de schema.

## Futuro

Si B36 o bloques posteriores necesitan formalizar campos nativos, esta capa de helpers permite migrar desde metadata a atributos explícitos sin romper UI ni IA: los callers seguirán usando el contrato de aplicación.
