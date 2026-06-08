# B44 — Vista concéntrica de anillos

## B44-T00 — Auditoría y diseño de layout concéntrico

Fecha: 2026-06-07
Agente: UI/UX Agent
Alcance: diseño técnico previo. No implementa código funcional.

---

## 1. Objetivo del bloque

B44 añade una vista visual de Creación donde los `WorldLayer`/Anillos causales existentes se representan como coronas concéntricas dinámicas:

- los anillos con `causal_rank` menor aparecen más cerca del centro;
- los anillos con `causal_rank` mayor aparecen hacia fuera;
- hojas, ramas, relaciones e hitos se colocan dentro de la corona que les corresponde;
- el usuario puede entrar en un anillo para trabajar solo con su contenido;
- la vista libre actual no debe romperse ni reescribirse.

B44 no crea un modelo paralelo. Usa:

- `Project.world_layers`;
- `WorldLayer.metadata["causal_rank"]` vía helpers de `packages.application.world_layer_causal`;
- `entity.layer_ids`;
- `relation.layer_ids` cuando esté disponible en el modelo de aplicación/servicio;
- filtros visuales efímeros (`VisualFilterState`), no canon.

---

## 2. Auditoría del estado actual

### 2.1 GraphCanvas / GraphCanvasView / GraphCanvasWidget

Archivo principal:

- `hosts/DesktopHostPySide/widgets/graph_canvas.py`

Estructura actual:

- `GraphCanvasWidget`: wrapper Qt con empty state, refresh desde proyecto y modo de anillos actual.
- `GraphCanvasView`: `QGraphicsView` interactivo. Gestiona escena, selección, drag, pan/zoom, filtros, búsqueda, foco y creación de relaciones.
- `GraphNodeItem`: hoja/entidad normal.
- `GraphTreeItem`: rama/contenedor visual.
- `GraphEdgeItem`: relación visual.

Puntos relevantes auditados:

- `GraphCanvasWidget.refresh()` construye `_NodeView` y `_EdgeView` desde `project.entities` y `project.relations`.
- `GraphCanvasWidget._layer_mode` se activa solo por acción explícita del usuario (`set_worldbuilding_active(True)` desde toolbar). Esto es importante: `project.worldbuilding_active` NO debe interpretarse como “mostrar vista de anillos”.
- `GraphCanvasView.set_graph(..., layer_mode=False, layers=None)` decide entre vista libre y vista por anillos/bandas.
- `GraphCanvasView.apply_visual_filter()` recompone el grafo con el mismo modo activo.
- `GraphCanvasView.focus_node()`, `focus_tree()`, `focus_relation()` y `focus_neighborhood()` centran/seleccionan usando items ya presentes.

Conclusión:

La vista concéntrica debe implementarse como un nuevo modo de layout dentro del canvas actual, no como una vista nueva independiente. Motivos:

1. Evita duplicar selección, filtros, búsqueda, relaciones y drag.
2. Respeta el contrato “no reescribir todo el canvas”.
3. Permite reutilizar `GraphNodeItem`, `GraphTreeItem`, `GraphEdgeItem`.
4. Mantiene el pipeline actual: proyecto → `_NodeView`/`_EdgeView` → items Qt.
5. Reduce riesgo de modelo paralelo.

Propuesta de modo:

```python
layout_mode: Literal["free", "layer_bands", "concentric_rings"]
```

En MVP B44 puede seguir usando booleanos internos si se minimiza el cambio, pero el diseño recomienda reemplazar gradualmente `_layer_mode_active: bool` por un enum/str efímero de UI para no confundir:

- vista libre;
- vista por bandas B36;
- vista concéntrica B44.

No se persiste como canon.

---

### 2.2 Representación actual de anillos B36

La vista por anillos actual está en:

- `GraphCanvasView._set_graph_by_layers(nodes, edges, layers)`

Comportamiento actual:

- usa `sort_layers_by_causal_rank(layers)`;
- descarta capas invisibles;
- descarta capas sin `causal_rank` para las bandas principales;
- crea bandas horizontales (`QGraphicsRectItem`) por capa;
- crea una banda “Sin anillo asignado” para nodos sin capa o con capa desconocida;
- coloca nodos en filas horizontales por `layer_id`;
- crea `GraphTreeItem` para entidades `entity_type == "contenedor"`;
- omite relaciones `contiene` como aristas visibles porque se expresan por contención visual;
- dibuja relaciones normales si ambos extremos están presentes.

Limitaciones actuales frente a B44:

- las bandas son lineales, no concéntricas;
- no hay modelo visual de corona con radio interior/exterior;
- no hay label anclado al borde de una corona;
- no hay hit testing de anillo como objeto seleccionable;
- no hay foco específico por anillo salvo filtro `layer_ids`;
- `_EdgeView` actual no expone `layer_ids`, aunque `relation.layer_ids` existe en persistencia/servicios;
- relaciones inter-anillo no tienen estilo específico;
- el tamaño de cada banda no depende de bounding boxes reales de ramas.

---

### 2.3 Cálculo de `causal_rank`

Fuente autorizada:

- `packages/application/world_layer_causal.py`

Funciones relevantes:

- `get_causal_rank(layer) -> int | None`
- `set_causal_rank(layer, rank)`
- `sort_layers_by_causal_rank(layers)`
- `validate_causal_metadata(layers)`
- `causal_layer_summary(layer)`

Contrato actual:

- `causal_rank` vive en `WorldLayer.metadata["causal_rank"]`.
- Se serializa como string para no cambiar el schema (`WorldLayer.metadata: dict[str, str]`).
- `get_causal_rank()` convierte a `int` o devuelve `None`.
- `sort_layers_by_causal_rank()` ordena:
  1. capas con rank, por rank ascendente;
  2. capas sin rank/meta, por `order` y nombre.

Para B44:

- rank menor = más central;
- rank mayor = más externo;
- capas sin rank o elementos sin capa van a una corona externa “Sin clasificar” / “No clasificado”.

No se debe leer `metadata["causal_rank"]` directamente en UI; usar siempre `get_causal_rank()` y `sort_layers_by_causal_rank()`.

---

### 2.4 Filtros y foco B37

Estado actual:

- `VisualFilterState` es efímero y no muta canon.
- Campos actuales:
  - `entity_types`
  - `relation_types`
  - `relation_families`
  - `tree_id`
  - `layer_ids`
  - `focus_entity_ids`
  - `canon_states`
  - `visibility_states`
  - `show_relations`
- `_node_passes_filter()` filtra por `layer_ids` usando `node.layer_id`.
- `_edge_passes_filter()` oculta aristas si algún extremo no está visible; esto ya evita handles/aristas flotantes.
- `focus_tree_scope()` usa `focus_entity_ids` con descendientes de rama.
- `focus_neighborhood()` incluye ancestros de contenedores para que no desaparezcan nodos dentro de ramas.
- `CreationWorkspace._set_focus_breadcrumb()` ya muestra estado y botón “Vista global”.

Para B44:

- entrar en anillo puede reutilizar `VisualFilterState(layer_ids=(ring_id,))` como base;
- conviene añadir un estado UI efímero `focused_ring_id` en `GraphCanvasWidget`/`CreationWorkspace` para breadcrumb, command bar y modo concéntrico;
- no es necesario persistir foco como canon;
- para IA B44-T07, `_current_context_scope()` debe añadir `active_ring_id` / `focused_ring_id` si existe.

---

### 2.5 Deuda de layout de ramas B34

Estado actual de `GraphTreeItem`:

- representa ramas como rectángulos con header fijo;
- soporta colapsar/expandir;
- contiene hijos visuales mediante `add_child_node()`;
- `resize_to_fit_children()` calcula tamaño según bounding boxes de hijos;
- relaciones `contiene` se expresan por contención visual, no como aristas;
- z-order actual:
  - ramas raíz: z negativo según profundidad;
  - hijos: z superior dentro de rama;
  - aristas/handles encima.

Deuda conocida relevante:

- layout interno de ramas es aproximado;
- puede haber solapes con muchos hijos o ramas anidadas;
- al usar ramas dentro de coronas, su bounding box debe ser respetado por el algoritmo concéntrico;
- no conviene reescribir esta lógica en B44;
- sí conviene medir `sceneBoundingRect()` / tamaño estimado del `GraphTreeItem` después de `resize_to_fit_children()` para reservar espacio angular suficiente.

---

## 3. Decisión de arquitectura B44-T00

### Decisión

Implementar la vista concéntrica como un modo de layout dentro del canvas actual.

Nombre propuesto:

```python
GraphCanvasView._set_graph_by_concentric_rings(nodes, edges, layers)
```

Activación desde `GraphCanvasWidget`:

```python
self._layout_mode = "free" | "layer_bands" | "concentric_rings"
```

Si se quiere minimizar diff inicial:

- mantener `_layer_mode` para bandas B36;
- añadir `_concentric_mode` para B44;
- asegurar exclusión mutua.

Pero el diseño recomendado a medio plazo es `layout_mode` único para evitar regresiones como confundir `worldbuilding_active` con modo visual.

### Por qué no vista nueva

No crear una vista nueva porque duplicaría:

- selección de nodos/relaciones;
- creación de relaciones por drag;
- filtros B37;
- búsqueda;
- foco de rama;
- estado visual de selección;
- paneles de detalle;
- toolbar y command bar.

---

## 4. Modelo visual efímero de coronas

B44 no añade modelo persistente. Puede añadir dataclasses internas al canvas:

```python
@dataclass
class _RingVisual:
    ring_id: str
    name: str
    rank: int | None
    color: QColor
    node_ids: list[str]
    relation_ids: list[str]
    leaf_count: int
    branch_count: int
    relation_count: int
    inner_radius: float
    outer_radius: float
    label_pos: QPointF
    visible: bool = True
    focused: bool = False
    collapsed: bool = False
```

Para “Sin clasificar”:

```python
ring_id = "__unclassified__"
rank = None
name = "Sin clasificar"
```

No se guarda en proyecto.

---

## 5. Orden de anillos del centro hacia fuera

Entrada:

- `project.world_layers`
- entidades con `entity.layer_ids`
- relaciones con `relation.layer_ids` o inferencia visual por extremos

Algoritmo:

1. Tomar capas visibles:
   ```python
   visible_layers = [l for l in layers if getattr(l, "is_visible", True)]
   ```
2. Ordenar con `sort_layers_by_causal_rank(visible_layers)`.
3. Separar:
   - ranked: `get_causal_rank(layer) is not None`
   - unranked/meta: rank `None`
4. Usar solo ranked para coronas causales principales.
5. Añadir corona externa “Sin clasificar” si existe al menos un elemento sin `layer_id`, con layer desconocido o en capa sin rank.

Regla:

- `causal_rank=1` → radio más cercano al centro.
- `causal_rank=N` → corona exterior acumulada.
- rank duplicado: ya lo detecta `validate_causal_metadata`; visualmente se ordena por rank y nombre para fallback, pero debe registrarse como límite/deuda si ocurre.

---

## 6. Asignación de elementos a anillos

### 6.1 Hojas y ramas

Regla principal:

```python
node_ring_id = node.layer_id
```

`_NodeView` actual solo toma el primer `layer_ids[0]`. Para B44-T04 esto es aceptable como MVP si se documenta, pero conviene revisar si una entidad puede pertenecer a varias capas. Opciones:

- MVP: usar la primera capa igual que B36.
- Futuro: permitir réplica visual o marcador multi-anillo sin duplicar entidad.

Asignación:

- Si `node.layer_id` pertenece a un `WorldLayer` visible y con rank → esa corona.
- Si no hay layer, layer desconocido o rank `None` → “Sin clasificar” externo.

### 6.2 Relaciones

`_EdgeView` actual no expone `layer_ids`. Para B44 se recomienda ampliar `_EdgeView` con:

```python
layer_ids: tuple[str, ...] = ()
```

sin cambiar persistencia, leyendo desde `relation.layer_ids`.

Clasificación visual:

- Intra-anillo:
  - ambos extremos tienen el mismo `ring_id`;
  - se dibuja dentro de la corona.
- Inter-anillo:
  - extremos tienen `ring_id` distinto;
  - se dibuja cruzando coronas;
  - si `relation_family(edge.kind) == "causal"`, puede tener estilo más direccional/sutil.
- Relación con un extremo oculto por filtro/foco:
  - se oculta; esto ya coincide con `_edge_passes_filter()`.
- Relación con `relation.layer_ids` propia:
  - si ambos extremos están en la misma corona, puede contarse como intra-anillo;
  - si sus extremos cruzan coronas, prima la topología visual por extremos para no dibujar handles flotantes.

---

## 7. Cálculo dinámico de radios

Objetivo: radios acumulados, sin solape entre coronas.

Constantes iniciales propuestas:

```python
CENTER_RADIUS_MIN = 160
RING_MIN_THICKNESS = 180
RING_PADDING_INNER = 42
RING_PADDING_OUTER = 52
ITEM_SPACING = 34
LABEL_RESERVED_ARC = 120
MAX_ITEM_DIAMETER_ESTIMATE = 260
```

### 7.1 Agrupar elementos

```python
rings = ordered_rings(layers)
nodes_by_ring = group_nodes(nodes)
edges_by_ring = classify_edges(edges, nodes_by_ring)
```

### 7.2 Estimar tamaño requerido por anillo

Para cada anillo:

- contar hojas;
- contar ramas;
- estimar área/bounding box de ramas;
- estimar espacio angular necesario.

MVP de estimación:

```python
leaf_size = 92
branch_size = max(tree_width, tree_height)  # o estimación 260 si aún no existe item
slot_sizes = [leaf_size for hojas] + [branch_size for ramas]
required_circumference = sum(slot_sizes) + ITEM_SPACING * count + LABEL_RESERVED_ARC
mid_radius_required = required_circumference / (2 * pi)
thickness_required = max(RING_MIN_THICKNESS, max(slot_sizes) + padding)
```

### 7.3 Radios acumulados

```python
inner = previous_outer + inter_ring_gap
outer = max(inner + thickness_required, mid_radius_required + thickness_required / 2)
mid = (inner + outer) / 2
```

Si un anillo crece, su `outer_radius` aumenta y los siguientes se desplazan hacia fuera porque su `inner` depende del `previous_outer`.

### 7.4 Evitar texto tapado

Cada corona reserva zona de label en el borde superior/izquierdo o tangente exterior.

Regla:

- label anclado al borde de la corona, no al centro;
- zona angular del label queda bloqueada para placement de items;
- el algoritmo de distribución angular empieza después de `LABEL_RESERVED_ARC`.

---

## 8. Posicionamiento de hojas y ramas dentro de la corona

Para cada anillo:

1. Calcular `mid_radius = (inner + outer) / 2`.
2. Distribuir slots angularmente.
3. Para cada item:
   ```python
   x = cos(angle) * mid_radius
   y = sin(angle) * mid_radius
   ```
4. Aplicar compresión vertical opcional solo si se mantiene estética actual; recomendado NO comprimir en modo concéntrico para que las coronas sean circulares.
5. Ramas (`GraphTreeItem`) se colocan por su centro visual, respetando bounding box.
6. Si hay pocos elementos:
   - 1 elemento: ángulo inferior derecho o centro de arco disponible, no encima del label;
   - 2-3 elementos: separación mínima angular.
7. Si hay muchos elementos (20-50): usar distribución por slots proporcional al tamaño.

### Ramas

B44 no reescribe layout interno de ramas. El flujo recomendado:

1. Crear todos los `GraphTreeItem`.
2. Poblar hijos usando lógica actual de `contiene`.
3. Ejecutar `resize_to_fit_children()`.
4. Medir `item.boundingRect()` / `sceneBoundingRect()` estimada.
5. Recalcular grosor de la corona si la rama no cabe.
6. Posicionar rama final dentro de la corona.

Para evitar ciclos de layout complejos, T02 puede hacer dos pasadas:

- pasada A: crear/medir items;
- pasada B: calcular radios y posiciones definitivas.

---

## 9. Render de coronas/anillos

### 9.1 Item visual recomendado

Crear un item interno:

```python
class GraphRingItem(QGraphicsPathItem):
    ring_id: str
    inner_radius: float
    outer_radius: float
```

Path:

- círculo exterior menos círculo interior;
- color sutil con alpha bajo;
- borde punteado/suave;
- z bajo.

Z-order propuesto:

- coronas: z = -100
- labels de corona: z = -90
- ramas: z = -10 + depth, como ahora, o z = 0 si hay conflicto
- hojas: z = 2
- relaciones: z = 10
- handles/drag overlays: z > 20

### 9.2 Label de anillo

Cada label debe incluir:

- nombre;
- contador: hojas / ramas / relaciones;
- indicador/botón “Entrar”.

MVP Qt:

- `QGraphicsSimpleTextItem` o `QGraphicsTextItem` para label;
- pequeño `QGraphicsRectItem` detrás como cápsula;
- opcional `GraphRingLabelItem` para hit testing del botón.

Texto sugerido:

```text
Metafísica · 3 hojas · 1 rama · 2 relaciones   Entrar
```

Anclaje:

- al borde superior de la corona;
- por ejemplo: `(-label_width/2, -outer_radius + 14)`;
- nunca en el centro.

### 9.3 Hit testing

Reglas:

- click en hoja/rama: selecciona hoja/rama;
- click en relación: selecciona relación;
- click en área vacía de corona: selecciona anillo o abre panel de anillo si existe;
- doble click en corona: entra en anillo.

Implementación:

- `GraphRingItem` con z bajo no debe bloquear clicks de items superiores;
- como está abajo, Qt prioriza items de z superior;
- si solo hay fondo de anillo bajo el cursor, `GraphCanvasView._item_ring_at()` puede detectar `GraphRingItem`;
- añadir señal efímera:
  ```python
  ringSelected = Signal(str)
  ringEnterRequested = Signal(str)
  ```

No mostrar IDs.

---

## 10. Entrada/salida de anillo

### 10.1 Acciones

- doble click en corona;
- botón/indicador “Entrar” en label;
- acción “Entrar en anillo” desde panel de anillo.

### 10.2 Modo foco

Usar filtro visual:

```python
VisualFilterState(layer_ids=(ring_id,))
```

Estado adicional UI:

```python
self._focused_ring_id = ring_id
```

Breadcrumb:

```text
Global > Anillo: Metafísica
```

Botón existente “Vista global” debe limpiar:

- filtros visuales;
- `_focused_ring_id`;
- breadcrumb;
- opcionalmente mantener modo concéntrico activo.

### 10.3 Relaciones vecinas atenuadas

MVP recomendado:

- ocultar relaciones cuyo extremo esté oculto, como ahora.

Futuro opcional:

- mostrar relaciones hacia anillos vecinos atenuadas requiere incluir nodos fantasma o endpoints visibles. No hacerlo en B44 MVP salvo que se defina claramente para evitar handles flotantes.

---

## 11. Compatibilidad con búsqueda, filtros y command bar

### 11.1 Búsqueda

`GraphCanvasView.search()` ya busca entidades y relaciones, incluyendo nombre de anillo si `worldbuilding_active=True`.

Para B44:

- `focus_search_result()` debe funcionar igual en modo concéntrico;
- si el resultado pertenece a un anillo no visible por foco actual, se debe:
  1. limpiar foco de anillo, o
  2. cambiar al anillo del resultado.

MVP recomendado:

- búsqueda global limpia foco visual antes de centrar si el item no existe en escena.

### 11.2 Filtros

Filtro por anillo puede usar `VisualFilterState.layer_ids`.

Importante:

- `_edge_passes_filter()` ya evita aristas flotantes si un extremo está oculto.
- Se debe conservar esta regla.

### 11.3 Command bar

`CreationWorkspace._current_context_scope()` ya envía:

- `active_layer_ids`
- `focus_label`
- selección
- filtros activos

B44-T07 debe añadir:

```python
"active_ring_id": self._focused_ring_id or "",
"focused_ring_id": self._focused_ring_id or "",
"layout_mode": "concentric_rings" | "layer_bands" | "free",
```

Cuando el prompt diga “en este anillo” o “dentro del anillo actual”, no hace falta IA profunda nueva: basta con pasar scope correcto al job.

---

## 12. Persistencia visual mínima

B44 puede ser completamente calculado.

Persistencia recomendada, si ya hay patrón para preferencias UI:

- última vista: libre / bandas / concéntrica;
- último anillo enfocado;
- cámara/zoom si ya existe soporte.

No persistir en canon:

- posiciones calculadas;
- radios;
- coordenadas angulares;
- colapsado visual de corona salvo preferencia UI explícita.

Si no hay soporte claro de preferencias UI, dejarlo efímero en B44 y documentar como deuda.

---

## 13. Cómo evitar romper la vista libre

Reglas de implementación:

1. No modificar el algoritmo de `set_graph(..., layer_mode=False)` salvo adaptaciones mínimas compartidas.
2. Añadir una función separada:
   ```python
   _set_graph_by_concentric_rings(...)
   ```
3. Mantener `_set_graph_by_layers()` para bandas B36, al menos durante B44.
4. No leer `project.worldbuilding_active` dentro de `refresh()` para decidir layout; solo gating de disponibilidad.
5. `worldbuilding_active` significa feature disponible, no modo visual activo.
6. Filtros y búsqueda deben operar sobre `_all_nodes`/`_all_edges`, no sobre items ya dibujados.
7. `apply_visual_filter()` debe recomponer usando el layout mode activo.
8. Si `Worldbuilding OFF`, ocultar/desactivar botón de vista concéntrica.

---

## 14. Hitos asociados

B44 menciona hitos asociados. Auditoría rápida:

- existen servicios/modelos de hitos causales (`causal_milestone_service.py`);
- no forman parte del canvas actual como item propio;
- B44 no debe inventar canon ni meter hitos como entidades si no están modelados así.

Diseño MVP:

- si hay hitos con `layer_ids`/`affected_layer_ids`, contarlos en el label de anillo si se puede acceder desde servicio sin acoplar UI a persistencia;
- no dibujar hitos como nodos hasta que exista contrato de visualización de hitos en canvas;
- si se dibujan en T03/T04, crear `GraphMilestoneItem` efímero ligado al modelo existente, no entidad paralela.

Límite conocido: B44-T00 no define implementación completa de hitos visuales porque el canvas actual solo maneja entidades y relaciones.

---

## 15. Plan por tickets

### B44-T01 — Modelo visual de anillos concéntricos

- Añadir dataclass interna `_RingVisual`.
- Añadir `GraphRingItem` si T03 lo necesita desde el inicio.
- Usar `WorldLayer` existente.
- Ordenar por `get_causal_rank()` / `sort_layers_by_causal_rank()`.
- Crear “Sin clasificar” externo.
- No tocar persistencia.

### B44-T02 — Layout concéntrico dinámico

- Implementar `_set_graph_by_concentric_rings()`.
- Agrupar nodos por anillo.
- Dos pasadas para medir ramas.
- Calcular radios acumulados.
- Distribuir por ángulo con slots según tamaño.
- Recalcular en cada `set_graph()`/filtro/refresh.

### B44-T03 — Render de coronas/anillos

- Dibujar `GraphRingItem` bajo nodos.
- Añadir labels anclados a borde.
- Añadir hit testing de corona.
- Añadir señales de selección/entrada de anillo.

### B44-T04 — Asignación visual de elementos a anillo

- Hoja/rama: `layer_ids[0]` como MVP.
- Relación: intra/inter por extremos; ampliar `_EdgeView.layer_ids` si hace falta para contador/contexto.
- Sin capa/rank: “Sin clasificar”.

### B44-T05 — Entrar en un anillo

- `focus_ring_scope(ring_id)` usando `VisualFilterState(layer_ids=(ring_id,))`.
- Breadcrumb `Global > Anillo: [nombre]`.
- Botón volver a global.
- Doble click y botón “Entrar”.

### B44-T06 — Relaciones intra/inter-anillo

- Clasificación visual por ring de extremos.
- Estilo causal/inter-anillo diferenciado.
- No edge bundling.
- Ocultar si algún extremo está oculto.

### B44-T07 — Filtros, búsqueda y command bar

- Búsqueda centra en su anillo.
- Filtro por anillo compatible con foco.
- Scope IA añade `active_ring_id` / `focused_ring_id`.

### B44-T08 — Persistencia visual mínima

- Evaluar si existe patrón de preferencias UI.
- Si no, mantener efímero y documentar deuda.

### B44-T09 — Smoke Windows

- Crear script/test específico B44 o ampliar script visual guiado.
- Validar el caso de 22 pasos indicado por el usuario.

---

## 16. Tests B44 recomendados

Unitarios/desktop específicos:

1. Orden de rings:
   - rank 1 aparece antes que rank 5;
   - rank None va a “Sin clasificar”.

2. Agrupación:
   - hoja con `layer_ids=[metafisica]` va a Metafísica;
   - rama con `layer_ids=[politica]` va a Política;
   - sin layer va a Sin clasificar.

3. Radios:
   - anillo con más elementos produce grosor/radio requerido mayor;
   - anillos externos se desplazan si uno interno crece.

4. Relaciones:
   - ambos extremos mismo ring → intra;
   - extremos distintos → inter;
   - filtro oculta relación si falta extremo.

5. Foco:
   - entrar en ring aplica `VisualFilterState(layer_ids=(ring_id,))`;
   - volver a global limpia filtro/foco.

6. Búsqueda:
   - buscar item en ring enfocado centra si visible;
   - buscar item fuera del foco gestiona el modo sin quedarse sin item.

Validaciones existentes a mantener:

```bash
python -m compileall hosts/DesktopHostPySide packages -q
python -m pytest tests/architecture/ -q
python scripts/run_all_tests.py --suites arch desktop infra sanity b33 b34 b35 b36 b37 b38 b39 b40 b41 b42
```

El usuario ejecuta la suite completa en Windows según regla de trabajo.

---

## 17. Límites conocidos

1. `GraphTreeItem` tiene deuda de layout interno; B44 debe medirlo, no reescribirlo.
2. `_NodeView` usa solo el primer `layer_ids`; multi-anillo queda fuera del MVP.
3. `_EdgeView` actual no incluye `layer_ids`; B44-T04/T06 debe ampliarlo si se necesitan contadores precisos o scope de relación.
4. Hitos causales no tienen item visual en canvas actual; contarlos/dibujarlos requiere contrato adicional.
5. No hay edge bundling; relaciones inter-anillo pueden cruzarse con muchos elementos.
6. Con 50+ elementos en una misma corona puede requerirse paginación visual o clustering futuro.
7. Persistir layout calculado no se recomienda en B44; si el usuario espera reabrir exactamente la misma cámara, hace falta patrón UI separado.
8. Labels largos de anillo pueden necesitar truncado/tooltip.
9. Ranks duplicados o inválidos deben validarse, pero el layout debe tener fallback estable.
10. La vista concéntrica depende de Worldbuilding ON; si Worldbuilding OFF, no debe aparecer.

---

## 18. Decisión final T00

B44 debe implementarse como modo de layout adicional dentro del canvas actual:

```text
Canvas actual + nuevo layout concéntrico calculado + items de fondo de corona
```

No como vista separada, no como modelo persistente nuevo, no como reescritura del canvas.

La primera implementación funcional debe concentrarse en:

1. estado efímero de layout mode;
2. agrupación por `WorldLayer` existente;
3. cálculo de radios acumulados;
4. render de `GraphRingItem` bajo nodos;
5. foco por anillo usando filtros existentes;
6. relación intra/inter por extremos.

Esto mantiene B44 alineado con contratos del proyecto: el core manda, el grafo es vista, la IA no canoniza, y la UI no crea modelo paralelo.
