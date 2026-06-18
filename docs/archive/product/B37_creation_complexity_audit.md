# B37-T00 — Auditoría de complejidad actual de Creación

Fecha: 2026-06-04
Estado: auditoría documental. No se tocó código de producción.

## 1. Objetivo de la auditoría

B37 busca que Creación siga siendo usable con grafos medianos/grandes. Esta auditoría revisa el estado real de la UI y del canvas antes de implementar búsqueda, filtros, foco, navegación, control de relaciones y bandeja de candidatos.

Archivos revisados:

- `hosts/DesktopHostPySide/widgets/graph_canvas.py`
- `hosts/DesktopHostPySide/views/workspaces.py`
- `hosts/DesktopHostPySide/widgets/node_detail_panel.py`
- `hosts/DesktopHostPySide/widgets/relation_detail_panel.py`
- `hosts/DesktopHostPySide/widgets/tree_detail_panel.py`
- `hosts/DesktopHostPySide/widgets/coherence_panel.py`
- `hosts/DesktopHostPySide/views/candidate_view.py`
- `hosts/DesktopHostPySide/views/workspaces.py` — `CandidateReviewPanel`
- B36 vista de capas causales en `graph_canvas.py` + `workspaces.py`

## 2. Resumen ejecutivo

Creación ya tiene una base útil:

- Canvas graph-first con nodos, árboles, relaciones seleccionables y drawer derecho.
- Selección múltiple para coherencia de subgrafo.
- Colapso/expansión visual de árboles.
- Botón de encajar todo.
- Vista de capas causales B36 si Worldbuilding ON.
- Candidatos IA ya aparecen en el grafo como nodos/aristas propuestas, y también existe una revisión limpia por tarjetas.
- CandidateView técnico existe con tabla, ocultación parcial de columnas técnicas en modo normal.

Pero para B37 faltan piezas centrales:

- No hay búsqueda usable dentro de Creación.
- No hay filtros visuales del grafo.
- No hay modo foco de árbol/subgrafo ni breadcrumb.
- No hay control visual de relaciones por familia/tipo.
- No hay centrar selección ni reset de vista; solo encajar todo.
- La bandeja de candidatos está duplicada y todavía mezcla una vista técnica con una tarjeta limpia parcial.
- La integración de candidatos estructurales B36 existe como previews/candidatos, pero no como bandeja enfocable desde el grafo.

Recomendación: B37 debe reutilizar `GraphCanvasWidget`, `GraphCanvasView`, `CandidateReviewPanel`, `CoherencePanel`, los `layer_ids` de B36 y los modelos `_NodeView`/`_EdgeView`. No debe reescribir el canvas ni crear modelos paralelos.

## 3. `graph_canvas.py`

### 3.1 Qué existe

#### Modelos de vista internos

- `_NodeView` resume entidad/candidato para canvas.
- `_EdgeView` resume relación/candidato para canvas.
- `_entity_view(entity)` incluye:
  - nombre,
  - tipo,
  - descripción breve,
  - canon,
  - visibilidad,
  - primera capa `layer_ids[0]`,
  - flag `proposed`.
- `_relation_view(relation)` incluye:
  - source/target,
  - tipo,
  - dirección,
  - color por metadata o por tipo.

Esto es reutilizable para búsqueda/filtros porque ya concentra los atributos visuales relevantes.

#### Candidatos en canvas

- `_candidate_is_pending_ai(candidate)` detecta candidatos IA pendientes.
- `_candidate_node_view(candidate)` crea nodos propuestos para candidatos con `proposed_data` de entidad.
- `_candidate_edge_view(candidate, known_entity_ids)` crea aristas propuestas si source/target existen.
- `GraphCanvasWidget.refresh()` añade candidatos IA pendientes al canvas.

Esto es útil para B37-T06, pero hoy no hay bandeja focalizada dentro del grafo ni acción “enfocar candidato”.

#### Árboles/colapso

- `GraphTreeItem` renderiza contenedores como rectángulos con header, contador y collapse indicator.
- `toggle_collapse()`, `_collapse()`, `_expand()` ocultan/recuperan descendientes.
- Al colapsar, se ocultan edges que involucran descendientes.
- `_refresh_edge_visibility()` evita aristas visibles si source/target no son visibles.

Esto es clave para B37-T01/T02/T04: la regla “no aristas flotantes” ya tiene una base.

#### Relaciones seleccionables

- `GraphEdgeItem` es `QGraphicsPathItem` seleccionable.
- La selección de relación emite `relationSelected` hacia `GraphCanvasWidget` y luego a `CreationWorkspace`.
- `selected_relation_ids()` existe en wrapper.

Esto permite implementar búsqueda de relaciones y foco de vecindad de relación sin modelo nuevo.

#### Selección de nodos/árboles

- `GraphCanvasWidget` expone:
  - `selected_entity_ids()`
  - `selected_relation_ids()`
  - `clear_selection()`
- `GraphCanvasView.focus_entity(entity_id)` centra y selecciona entidad/árbol si existe.

`focus_entity()` es una base mínima para búsqueda, pero hoy es insuficiente: no expande ruta si está dentro de árbol colapsado, no abre panel por sí mismo desde una búsqueda, no hace zoom suave, no resalta relaciones asociadas.

#### Vista de capas B36

- Importa `get_causal_rank` y `sort_layers_by_causal_rank`.
- `GraphCanvasWidget.set_worldbuilding_active(active)` refresca el canvas.
- `refresh()` activa `layer_mode` si `project.worldbuilding_active`.
- `set_graph(..., layer_mode=True, layers=...)` usa layout por capas.
- Las capas superiores quedan arriba y se añade banda “Sin capa asignada”.

Esto cumple B36 MVP y debe reutilizarse para filtros por capa en B37.

#### Cámara

- `GraphCanvasWidget._fit_all()` encaja todos los items del scene.
- La toolbar inferior llama a `_fit_all()`.
- El canvas usa `fitInView()` tras reconstruir grafo.

Base para B37-T05, pero faltan botones dedicados a centrar selección y reset.

### 3.2 Qué está visible en UI

- Nodos, árboles y relaciones del proyecto.
- Candidatos IA pendientes como elementos propuestos en canvas.
- Colapso de árbol mediante header/indicador.
- Selección de nodos/relaciones.
- Vista por capas cuando Worldbuilding ON.
- Botón de encajar todo en barra inferior.

### 3.3 Qué está oculto

- IDs completos se guardan internamente, no se muestran en canvas normal.
- `advanced_mode` solo loguea IDs en selección; en modo normal se ocultan.
- No hay controles visibles para filtros/search/foco.
- No hay indicador de filtros activos porque no existen filtros.

### 3.4 Qué está duplicado o disperso

- Candidatos se ven en canvas como propuestas y también en `CandidateReviewPanel`/`CandidateView`.
- El control de visibilidad de edges existe dentro de árboles, pero no como política global de filtros.
- Vista de capas se activa vía botón B36 y también automáticamente por `worldbuilding_active` en refresh; esto puede ser confuso si en B37 se añaden más vistas.

### 3.5 Qué es técnico y debe ocultarse

- IDs en logs cuando `advanced_mode=True` son aceptables, pero no deben aparecer en normal.
- Candidate IDs técnicos ya aparecen truncados en `CandidateView` si modo avanzado; ocultos en modo normal por `set_columns_visible`.
- No deben exponerse `_NodeView`, `_EdgeView`, JSON de candidates ni `proposed_data` en UI normal.

### 3.6 Qué puede reutilizarse

- `_NodeView` / `_EdgeView` como base para búsqueda/filtros.
- `focus_entity()` como base para centrar búsqueda.
- `_refresh_edge_visibility()` para garantizar no aristas flotantes.
- `selected_entity_ids()` / `selected_relation_ids()` para vecindad/foco.
- `GraphTreeItem` descendants para detectar miembros ocultos por collapse.
- `layer_id` en `_NodeView` para filtro por capa.
- `edge.kind` para filtro por tipo/familia de relación.

### 3.7 Qué falta para B37

- Estado de filtros visuales en `GraphCanvasWidget` o value object simple.
- API pública de canvas para:
  - buscar elementos,
  - seleccionar/centrar entidad,
  - seleccionar/centrar relación,
  - encajar todo,
  - reset vista,
  - centrar selección,
  - activar foco de subgrafo,
  - limpiar foco/filtros.
- Aplicar filtros antes de crear `GraphNodeItem`/`GraphEdgeItem` o durante rebuild.
- Mantener relaciones ocultas si source/target están ocultos.
- Resaltado de relaciones asociadas a selección.
- Familia de relación: estructural / narrativa / causal / coherencia-incidencia.

## 4. `workspaces.py` — CreationWorkspace

### 4.1 Qué existe

#### Estructura general

- `CreationWorkspace` es graph-first.
- Tiene canvas central `GraphCanvasWidget`.
- Usa drawer derecho para paneles, no ventanas externas.
- Conecta señales:
  - `entitySelected` → `_open_node_panel`
  - `relationSelected` → `_open_relation_panel`
  - `relationCreateRequested` → `_open_relation_create_panel`
  - `graphSelectionChanged` → `_on_graph_selection_changed`
  - `nodeAssignToTreeRequested` → `_assign_node_to_tree`

#### Toolbar inferior

Controles visibles actuales:

- Crear entidad.
- Crear contenedor/árbol.
- Sugerir entidad con IA.
- Sugerir relación con IA.
- Analizar coherencia de selección.
- Vista Capas causales si Worldbuilding ON.
- Eliminar selección.
- Enfocar todo.

#### Coherencia de selección

- `_on_graph_selection_changed()` activa/desactiva botón de coherencia, delete y tooltips con conteo de nodos/relaciones.
- `_open_coherence_panel()` abre `CoherencePanel` sobre selección actual.

#### B36 vista capas

- `_layers_view_btn` visible solo si Worldbuilding ON.
- `_activate_layers_view()` loguea “Vista Capas causales activa” y fuerza refresh de graph con worldbuilding active.

#### CandidateReviewPanel limpio

Dentro de `workspaces.py` existe `CandidateReviewPanel`:

- Título “Sugerencias”.
- Lista candidatos como tarjetas, no tabla.
- Acciones aceptar/rechazar.
- Se usa desde entrada normal “Sugerencias”.

Esto es la base más cercana para B37-T06.

### 4.2 Qué está visible en UI

- Barra inferior siempre visible con iconos.
- Barra superior hover, pero no relevante para B37 salvo que se aproveche para controles discretos.
- Botón de capas B36 solo si Worldbuilding ON.
- Botón coherencia solo se habilita si hay selección.
- Botón delete solo se habilita si hay selección.

### 4.3 Qué está oculto

- No existe icono de búsqueda.
- No existe icono de filtros.
- No existe breadcrumb de foco.
- No existe indicador de filtros activos.
- No existe “volver a global”.
- No existe “centrar selección”.
- No existe “reset vista”.

### 4.4 Qué está duplicado

- `CandidateReviewPanel` limpio dentro de Creación y `CandidateView` técnico fuera/como vista conectada.
- Capas se gestionan en `NarrativeWorkbench` como tarjeta “Capas” y en toolbar como “Vista Capas causales”. Son funciones distintas, pero pueden confundirse; B37 debe nombrarlas claramente.

### 4.5 Qué es técnico y debe ocultarse

- Tooltips normales son limpios.
- Logs de IDs dependen de advanced_mode en canvas.
- CandidateReviewPanel no muestra IDs; debe preferirse para modo normal.

### 4.6 Qué puede reutilizarse

- Barra inferior para iconos discretos de búsqueda/filtros/foco/cámara.
- Drawer derecho para paneles de búsqueda/filtros/candidatos sin modales.
- `_on_graph_selection_changed()` para actualizar estado de relaciones resaltadas y centrar selección.
- `CandidateReviewPanel` para B37-T06, ampliándolo con foco/ver contexto.

### 4.7 Qué falta para B37

- Panel drawer de búsqueda.
- Panel drawer de filtros.
- Estado de foco y breadcrumb visible.
- Acciones “Enfocar árbol” y “Enfocar vecindad” desde paneles.
- APIs en workspace para mandar al graph: focus/filter/search.

## 5. `node_detail_panel.py`

### 5.1 Qué existe

- Panel de entidad en drawer.
- Campo “Capa” visible solo si Worldbuilding ON.
- Autosave programado para campos principales, incluido layer combo.
- IA inline de texto con aceptar/descartar/refinar.
- Botón “Analizar coherencia”.
- B36:
  - combo “Destino causal”,
  - “Expandir hacia capa inferior”,
  - “Explicar desde causas superiores”.
- Las acciones B36 son candidate-producing y no canonizan directamente.

### 5.2 Qué está visible

- Campos de identidad/tipo/descripción.
- Capa si Worldbuilding ON.
- IA inline.
- Coherencia.
- Acciones causales B36 si Worldbuilding ON.

### 5.3 Qué está oculto

- No hay acción “Enfocar vecindad”.
- No hay acción “Centrar en grafo”.
- No hay indicadores de filtros/foco aplicados desde panel.

### 5.4 Qué está duplicado

- IA inline textual y acciones B36 candidate-producing comparten el frame de sugerencia. Esto puede ser aceptable temporalmente, pero B37-T06 pide no mezclar sugerencias inline de texto con candidatos estructurales. Debe separarse la bandeja de candidatos estructurales.

### 5.5 Qué es técnico y debe ocultarse

- No se ven IDs/JSON en modo normal.
- El prompt/hint B36 no debe exponerse como texto técnico; hoy solo se usa internamente.

### 5.6 Qué puede reutilizarse

- Botón/área de IA inline para texto.
- Estado de Worldbuilding para mostrar controles de capa/foco causal.
- Contexto de entidad para búsqueda y vecindad.

### 5.7 Qué falta para B37

- Botón “Enfocar vecindad”.
- Botón discreto “Centrar en grafo” si se decide en panel.
- Señal/callback hacia workspace para activar foco sin modificar canon.
- Separar acciones B36 estructurales hacia bandeja de candidatos si generan Candidate real.

## 6. `tree_detail_panel.py`

### 6.1 Qué existe

- Panel de árbol/contenedor con secciones:
  - identidad,
  - función narrativa,
  - contenido,
  - worldbuilding/canon,
  - IA.
- Listas de:
  - miembros,
  - subárboles,
  - relaciones internas,
  - relaciones externas.
- Combo “Capa causal” si Worldbuilding ON.
- IA de descripción/miembros/subárboles/coherencia/preguntas.
- B36:
  - destino causal,
  - expandir hacia capa inferior,
  - explicar desde causas superiores.

### 6.2 Qué está visible

- Miembros y subárboles ya se muestran como listas limpias.
- Relaciones internas/externas se muestran en el panel del árbol.
- Capa causal visible solo si Worldbuilding ON.

### 6.3 Qué está oculto

- No hay acción “Enfocar árbol”.
- No hay breadcrumb “Global > ...”.
- No hay “volver a global”.
- No hay acción para enfocar relación interna/externa listada.

### 6.4 Qué está duplicado

- Coherencia en tree panel aparece como acción IA de árbol, pero también existe `CoherencePanel` general para selección de grafo. Debe unificarse conceptualmente en B37: foco/selección de árbol debería abrir coherencia sobre el subgrafo visible o sus miembros.

### 6.5 Qué es técnico y debe ocultarse

- Los miembros/subárboles se muestran por nombre, no IDs: correcto.
- No exponer relación interna como ID; mantener nombres/tipos legibles.

### 6.6 Qué puede reutilizarse

- Listas de miembros/subárboles para construir foco de árbol.
- Relaciones internas/externas para modo foco.
- `membershipChanged` ya comunica cambios de pertenencia.

### 6.7 Qué falta para B37

- Acción “Enfocar árbol”.
- Acción “Enfocar vecindad” para el árbol.
- Breadcrumb de ruta jerárquica.
- Opción de expandir ruta si un resultado está dentro de árbol colapsado.

## 7. `relation_detail_panel.py`

### 7.1 Qué existe

- Panel de relación en drawer.
- Tipo de relación editable desde enum `RelationType`, incluyendo tipos causales B36 porque enumera valores reales.
- IA inline específica de relación.
- Botón “Analizar coherencia” que abre `CoherencePanel` con la relación y sus endpoints.
- Persistencia incluye `layer_ids` en payload.
- No usa ventanas externas para detalle/coherencia.

### 7.2 Qué está visible

- Tipo, origen/destino, dirección/intensidad, descripción y campos narrativos.
- IA inline.
- Coherencia de relación.

### 7.3 Qué está oculto

- No hay “Enfocar vecindad de relación”.
- No hay control para centrar arista en canvas.
- No hay familia de relación visible: estructural/narrativa/causal.

### 7.4 Qué está duplicado

- El tipo causal está en enum y en colores del canvas; falta mapping central de familia para UI/filtering.

### 7.5 Qué es técnico y debe ocultarse

- En modo normal no deben mostrarse IDs de endpoints; usar nombres mediante `human_ref`/nombres.
- No mostrar JSON de metadata/layer_ids.

### 7.6 Qué puede reutilizarse

- Endpoints de relación para foco de vecindad.
- `relation_type` para filtros por tipo/familia.
- CoherencePanel ya sabe analizar relación + endpoints.

### 7.7 Qué falta para B37

- Acción “Enfocar vecindad”.
- API canvas para seleccionar/centrar relación.
- Familia de relación reusable para filtro y estilo.

## 8. `coherence_panel.py`

### 8.1 Qué existe

- Panel en drawer para coherencia conjunta.
- Recibe `entity_ids` y `relation_ids` seleccionados.
- Ejecuta análisis IA sin canonizar.
- Genera reparación como sugerencia.
- Solo aplica reparación al aceptar explícitamente.
- Al aplicar, solo modifica campos permitidos:
  - entidades: descripción/notas/tags,
  - relaciones: descripción/temporalidad/causalidad/condiciones/source.
- No crea nodos ni relaciones.

### 8.2 Qué está visible

- Conteo de selección.
- Estado de análisis.
- Informe.
- Selector de motivo/propuesta de reparación.
- Caja de instrucción opcional.
- Botones generar reparación, descartar y aceptar/aplicar.

### 8.3 Qué está oculto

- No hay foco visual del subgrafo analizado desde el panel.
- No hay botón “ver en grafo” o “enfocar selección analizada”.
- No hay vínculo a filtros/subgrafo cercano.

### 8.4 Qué está duplicado

- Coherencia accesible desde toolbar, nodo, relación y árbol. Esto es útil, pero B37 debería asegurar que todas las entradas abren el mismo panel con selección/foco coherente.

### 8.5 Qué es técnico y debe ocultarse

- El patch JSON se espera en la respuesta IA para aplicar reparación. En modo normal esto puede aparecer en el preview si la IA lo devuelve. B37 debería ocultar/plegar el bloque técnico y mostrar una versión humana.

### 8.6 Qué puede reutilizarse

- Selección de subgrafo para modo foco.
- Mecanismo no-canon hasta aceptación explícita.
- Status inline sin modales.

### 8.7 Qué falta para B37

- Foco de subgrafo desde coherencia.
- Relación con filtros activos.
- Ocultación humanizada del patch técnico.

## 9. Candidate/import views conectadas a Creación

### 9.1 `CandidateReviewPanel` en `workspaces.py`

Existe una vista limpia de sugerencias:

- Tarjetas.
- Título y resumen.
- Botones aceptar/rechazar.
- Empty state limpio.
- No muestra IDs.

Limitaciones:

- No muestra tipo estructural claro: nodo/relación/árbol/causalidad/coherencia.
- No muestra origen con suficiente detalle humano.
- No muestra estado aceptada/descartada salvo lo que devuelva el listado.
- No tiene “enfocar en grafo”.
- No tiene “ver contexto”.
- No separa candidatos estructurales de sugerencias inline de texto.

### 9.2 `CandidateView`

Existe vista técnica/tabla:

- `QTableWidget` con columnas ID, título, tipo, estado, origen.
- En modo normal oculta columnas ID y origen mediante `set_columns_visible`.
- Detalle avanzado muestra metadata y proposed_data.
- Aceptar/rechazar llama al controller.

Problemas para B37 normal:

- Sigue siendo tabla, no bandeja visual.
- Tipo/estado aparecen con valores enum crudos (`candidate_type.value`, `state.value`).
- En modo avanzado muestra datos técnicos; correcto para QA, no para normal.
- No enfoca en grafo.

### 9.3 Import views

La auditoría no encontró una integración de importación documental avanzada dentro del flujo normal de Creación que sea relevante para B37. Debe quedar fuera de alcance según el contrato del bloque.

## 10. B36 vista de capas

### 10.1 Qué existe

- Botón “Vista Capas causales” (`▤`) en barra inferior.
- Visible solo con `Worldbuilding ON`.
- `GraphCanvasWidget.refresh()` activa `layer_mode` si `worldbuilding_active`.
- El canvas agrupa elementos por bandas según capa causal.
- Elementos sin capa caen en “Sin capa asignada”.

### 10.2 Qué está visible

- Bandas/capas causales en el grafo.
- Nodos/árboles ubicados por capa.
- Estilo causal de relaciones B36.

### 10.3 Qué está oculto

- No hay filtro por capa todavía.
- No hay contador por capa.
- No hay limpiar vista de capas si se quiere volver a otro layout salvo refresh/global.

### 10.4 Qué puede reutilizarse

- `layer_id` de `_NodeView`.
- `sort_layers_by_causal_rank`.
- `worldbuilding_active` para mostrar controles de filtros de capa solo si procede.

## 11. Duplicidades y riesgos actuales

1. **Candidatos duplicados:** aparecen en canvas como propuestas y en paneles/listados de candidatos. B37-T06 debe consolidar experiencia normal.
2. **Coherencia multi-entrada:** toolbar, nodo, relación y árbol pueden disparar coherencia. Correcto, pero falta un modelo común de foco/subgrafo.
3. **Capas como gestión vs vista:** “Capas” en workbench crea/gestiona capas; “Vista Capas causales” cambia layout. Etiquetas deben ser claras.
4. **Patch JSON visible en coherencia:** riesgo técnico en UI normal.
5. **Logs con IDs en modo avanzado:** aceptable, pero no deben filtrarse al modo normal.
6. **Candidatos estructurales vs texto inline:** actualmente pueden compartir área de sugerencia en paneles. B37 debe separarlos.

## 12. Qué falta por ticket B37

### B37-T01 — Buscar y enfocar elementos del grafo

Falta:

- Panel/buscador discreto.
- Índice de búsqueda sobre entidades, árboles, capas y relaciones.
- Resultados como lista limpia.
- Foco de entidad/árbol usando `focus_entity()` extendido.
- Foco de relación nuevo.
- Detección de resultado dentro de árbol colapsado.
- Acción expandir ruta o enfocar árbol.

Reutilizar:

- `_NodeView`, `_EdgeView`, `focus_entity()`, selección signals, drawer.

### B37-T02 — Filtros por tipo, capa, árbol, estado y visibilidad

Falta:

- Estado de filtros no persistente.
- Panel de filtros.
- Indicador de filtros activos.
- Botón limpiar filtros.
- Filtro por tipo entidad, tipo relación, árbol, capa, canon, visibilidad.
- Ocultar relación si source/target ocultos.

Reutilizar:

- `_NodeView.kind`, `canon`, `visibility`, `layer_id`.
- `_EdgeView.kind`.
- `_refresh_edge_visibility()`.
- Relaciones `contiene` para árbol/contenedor.

### B37-T03 — Vista enfocada de árbol/subgrafo

Falta:

- Acción “Enfocar árbol” en tree panel.
- Acción “Enfocar vecindad” en nodo/relación.
- Estado de foco en workspace/canvas.
- Breadcrumb.
- Volver a global.

Reutilizar:

- `TreeDetailPanel` members/subtrees/internal/external relations.
- `GraphTreeItem` descendants.
- `selected_entity_ids()`/`selected_relation_ids()`.

### B37-T04 — Control visual de relaciones

Falta:

- Toggle global mostrar/ocultar relaciones.
- Filtro por tipo/familia.
- Atenuar no seleccionadas.
- Resaltar relaciones de nodo seleccionado.
- Mapping central de familia:
  - estructural: `contiene` / pertenencia si existe,
  - causal: tipos B36,
  - narrativa: resto de RelationType narrativos,
  - coherencia/incidencias si se representan como relation/candidate.

Reutilizar:

- `_EDGE_COLORS`.
- `GraphEdgeItem.set_selected_style()`/pen si existe.
- `edge.kind`.
- Endpoint visibility.

### B37-T05 — Navegación de cámara

Falta:

- Botón centrar selección.
- Botón reset vista.
- Foco suave/zoom al buscar/enfocar.
- API pública no privada para `fit_all`.

Existe:

- Botón “Enfocar todo” conectado a `_fit_all()`.
- `focus_entity()` básico.

### B37-T06 — Bandeja de sugerencias/candidatos IA

Falta:

- Bandeja unificada dentro de Creación.
- Tipo visual nodo/relación/árbol/causalidad/coherencia.
- Estado pendiente/aceptada/descartada humanizado.
- Enfocar en grafo.
- Ver contexto.
- Separar candidatos estructurales de sugerencias inline.

Reutilizar:

- `CandidateReviewPanel` por tarjetas.
- `CandidateController.accept/reject`.
- Candidatos del canvas.

### B37-T07 — Smoke de proyecto mediano y cierre

Falta:

- Fixture/proyecto de prueba mediano.
- Tests B37 específicos.
- Suite B37 en `scripts/run_all_tests.py`.
- Checklist visual Windows.

Reutilizar:

- Tests B33/B34/B35/B36 como referencias.
- `run_all_tests.py` suite registry.

## 13. Recomendación de orden

Orden recomendado:

1. B37-T01 búsqueda + foco básico.
2. B37-T05 cámara mínima junto a T01, porque buscar necesita centrar/zoom.
3. B37-T02 filtros visuales.
4. B37-T04 control de relaciones, apoyado en filtros.
5. B37-T03 foco de árbol/subgrafo y breadcrumb.
6. B37-T06 bandeja de candidatos.
7. B37-T07 smoke mediano/cierre.

Motivo: búsqueda/foco/cámara dan valor inmediato y establecen APIs que filtros/foco/subgrafo reutilizan.

## 14. Decisiones de arquitectura recomendadas para B37

1. **Filtros son vista, no dominio.** No persistir filtros en el proyecto en MVP.
2. **No mutar canon.** Search/focus/filter nunca llaman servicios de escritura.
3. **No modelo paralelo.** Usar `NarrativeEntity`, `NarrativeRelation`, `Candidate`, `WorldLayer`.
4. **No reescribir canvas.** Añadir APIs incrementales a `GraphCanvasWidget`/`GraphCanvasView`.
5. **Sin ventanas externas.** Usar drawer/inline panels.
6. **Sin IDs/JSON en normal.** Technical details solo en advanced mode.
7. **No aristas flotantes.** Toda relación visible debe tener source y target visibles.
8. **Candidatos no canon.** Aceptar siempre mediante `CandidateController`/servicios reales.

## 15. Checklist mínima antes de implementar B37-T01

Antes de tocar código:

- Confirmar ticket Kanban B37-T01 aprobado explícitamente.
- Cargar `narrative-architect-agents` + `na-ui-agent` + `na-qa-agent`.
- Crear rama por ticket si procede: `feature/B37-T01-search-focus`.
- Definir API pública en canvas:
  - `focus_entity(entity_id)` extendido o wrapper público.
  - `focus_relation(relation_id)` nuevo.
  - `fit_all()` público.
- Definir panel drawer de búsqueda sin `QDialog`.
- Añadir tests específicos B37 y registrar suite.

## 16. Estado final de T00

B37-T00 queda completado como auditoría documental. No se modificó código de producción.

Entregable:

- `docs/product/B37_creation_complexity_audit.md`
