# BETA1-UX4 — Diagnóstico de los comandos de la command bar

Diagnóstico end-to-end **con proveedor real** (Z.ai `glm-5.1`) usando el arnés
[scripts/diagnose_command_matrix.py](../../scripts/diagnose_command_matrix.py). Cubre los
25 pares Acción×Ámbito ejecutando un caso por **AIJobType distinto** (analizar/explicar/
expandir son scope-agnósticas → una cubre su fila; editar:hoja == editar:rama).

Camino trazado por par: `plan_command_jobs → create_job → execute_job → salida del
modelo → stage_results → candidato → accept_candidate → canon → veredicto de render`.

## Resumen por comando

| Par (job) | Estado | Síntoma observado |
|---|---|---|
| Crear Hoja (`generate_entities`) | ⚠️ casi | Crea hojas OK (`personaje`→hoja). Pero si el modelo usa un `entity_type` fuera de la taxonomía (p.ej. `concepto`), se coacciona en silencio a `nota`. |
| Crear Rama (`generate_tree`) | ❌ | El modelo da ramas con tipo semántico (`institucion`, `religion`); **el render las dibuja como hoja**. Además devuelve hojas planas sin pertenencia (no `contiene`). |
| Crear Relación (`suggest_relations`) | ❌ | El modelo devuelve `source_name`/`target_name` que **no casan** con las entidades seleccionadas → `accept` falla: "No se pudieron encontrar las entidades para esta relación". |
| Crear Anillo (`create_ring_template`) | ✅ | Crea anillos (plantilla de estratos). |
| Crear Hito (`propose_milestones`) | ✅ | Crea el hito. |
| Editar * (`edit_entities/relation/ring/milestone`) | ❌ | Aceptar un candidato de edición **no cambia nada en canon**: las ediciones se stagean como `sugerencia_ia` y `accept_candidate` no tiene rama para aplicarlas (`else: pass`). |
| Analizar (`analyze_coherence`) | ✅ | Produce informe revisable; no muta canon (correcto por diseño). |
| Explicar (`explain_from_causes`) | ❌ | Debería crear hitos/entidades o editar referenciadas; produjo solo un informe genérico y **no creó nada**. |
| Expandir (`expand_worldbuilding`) | ❌ | **0 candidatos stageados**: no produjo nada accionable. |

## Causas raíz confirmadas

### C1 · Render decide contenedor con un test demasiado estrecho (Crear Rama)
El grafo dibuja contenedor sólo si `entity_type == "contenedor"` exacto
([graph_canvas.py:3878](../../hosts/DesktopHostPySide/widgets/graph_canvas.py#L3878),
[:3368](../../hosts/DesktopHostPySide/widgets/graph_canvas.py#L3368), y layout libre).
`node.kind` sale de `entity_type` en [_entity_view](../../hosts/DesktopHostPySide/widgets/graph_canvas.py#L322).
No mira `display_type`, `candidate_tree` ni `BRANCH_TYPES`. Dato real: ramas
`institucion`/`religion` → render `hoja`. Incoherente con `command_expansion._is_branch`.

### C2 · `display_type` se pierde al aceptar
[NarrativeEntity.from_dict](../../packages/domain/entity.py#L238) no lee `display_type`;
el staging lo pone en la raíz del candidato ([ai_jobs.py:807](../../packages/application/ai_jobs.py#L807)).
Tras canon sólo sobreviven `entity_type` y `custom_metadata.candidate_tree`.

### C3 · Tipos fuera de taxonomía degradan a `nota`
El modelo devuelve `entity_type` libres (`concepto`); `_parse_enum` los coacciona a
`NOTA` sin avisar. El prompt no fija la lista exacta de `EntityType` válidos.

### C4 · Crear Rama no materializa contención
`generate_tree` devuelve hojas y ramas como listas planas; al aceptar **no se crean
relaciones `contiene`**. Una rama nace como contenedor vacío y las hojas flotan sueltas.

### C5 · Editar no se aplica nunca
Las ediciones se stagean como `sugerencia_ia` (estructuradas: `edit_target_name`/
`edit_field`/`edit_proposed_value`, o un informe genérico). `accept_candidate`
([candidate_service.py:150](../../packages/application/candidate_service.py#L150)) sólo
materializa ENTIDAD / RELACION / `causal_milestone` / `ring_template` / cronología; para
las ediciones cae en `else: pass`. **No hay ruta para aplicar una edición a canon.**

### C6 · Crear Relación no resuelve los extremos
El modelo nombra entidades (`source_name`/`target_name`) que no coinciden con las
seleccionadas; `_resolve_relation_endpoints_by_name` falla. No se pasan al modelo los
nombres/ids exactos de la selección para forzar que relacione ESAS entidades.

### C7 · Explicar/Expandir no producen salida accionable
Sus system prompts / `stage_results` no están alineados con el comportamiento de la
matriz (crear hitos/entidades, o editar referenciadas). Resultado real: Explicar sólo
informe; Expandir 0 candidatos. (Requiere revisar `command_prompts` + `stage_results`
por intent; en parte puede ser elicitación del modelo, a confirmar al arreglar.)

## Decisiones de diseño ya tomadas con el usuario
- **Rama = contenedor real.** Representación canónica elegida: **forzar
  `entity_type=contenedor`** en la rama; el tipo semántico (religion/institucion…) se
  guarda aparte en `custom_metadata`. Esto hace que el render actual (`=="contenedor"`)
  ya la dibuje como contenedor; se ampliará el test igualmente por robustez.

## Resultado tras los arreglos (confirmado con proveedor real)

| Causa | Arreglo | Verificación (real) |
|---|---|---|
| C1/C2 | Staging fuerza `entity_type=contenedor`; tipo semántico + `display_type` a `custom_metadata` | `crear:rama` → `contenedor=>cont` |
| C4 | `generate_tree` anida hojas por rama; `accept_candidate` crea hijas + `contiene` | rama con `children_contiene=5` |
| C5 | `accept_candidate` aplica ediciones a canon (entidad/relación/anillo/hito) | `editar:*` → `editado:entity/relation/ring` |
| C6 | Staging usa el `fanout_pair` (ids reales) en vez de nombres del modelo | `crear:relacion` → `relacion` creada |
| C3 | `normalize_entity_type` (sinónimos→EntityType) en `from_dict` + prompts con taxonomía válida | `concepto`→`regla_del_mundo`; `crear:hoja` sin degradar |
| C7 | **No era bug de código**: faltaba RAG en el arnés (el modelo no veía la selección). Con RAG ya funcionan; se explicitó el FORMATO por robustez | `explicar` crea hitos+hojas; `expandir` crea hojas+relaciones |

Hallazgo clave de método: el diagnóstico inicial corría el arnés **sin RAG** (rag_service=None),
lo que hacía parecer rotos a Editar/Explicar/Expandir (el modelo no recibía el texto de la
selección). Con RAG cableado (como en la app real) varios "fallos" desaparecen; los reales eran
C1–C4 y C6.

## Notas
- `scripts/diagnose_command_matrix.py` queda como herramienta de regresión: cablea servicios +
  RAG real e índice del proyecto. Re-ejecutar por par tras cada cambio. La API key vive sólo en
  `.env.local` (ignorado por git).
- Pares ✅ (Crear Anillo/Hito, Analizar) se usan como control: deben seguir verdes.
- Tests deterministas (sin modelo) en `tests/application/test_ux4_command_fixes.py`.
