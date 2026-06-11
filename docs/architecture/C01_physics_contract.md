# C01 — Contrato real de física visual (Fase C)

Fecha: 2026-06-11 · Rama: `feature/BETA1-C01` · Base: cierre de B03

## 1. Estado real del código (auditoría)

| Punto auditado | Resultado |
|---|---|
| `packages/ui/graph_physics/` | **Existe pero está VACÍO** (0 archivos, ni `__init__.py`) |
| `engine.py`, `state.py`, `forces.py`, `ring_layout.py`, `branch_cluster.py`, `canvas_bridge.py`, `concentric_layout_state.py`, `concentric_invariants.py` | **No existen** |
| Tests de física | **No existen** (`pytest -k physics` recoge 0; `tests/ui/` solo tiene tests estáticos CLI/B3x) |
| `_physics_enabled` | **No existe en código** (solo en docs/kanban) |
| `_toggle_physics_mode` | No existe |
| `_clamp_items_to_current_rings` | No existe |
| `"concentric_physics"` | **No existe en código** — solo en documentación histórica. Requisito "eliminarlo" se cumple por vacuidad |
| `_layout_mode` / `_layout_mode_active` | Existen y sanos: `GraphCanvasWidget._layout_mode` (persistido en ctx) y `GraphCanvasView._layout_mode_active` ∈ {free, layered, concentric_rings} |
| Referencia de HANDOFF.md a "graph_physics (concentric_physics + free physics)" | **Intención histórica, no realidad.** B46/B47 no están en este linaje del repo |
| Bugs B46/B47 heredados | Ninguno: no hay física que los contenga. Los 7 fallos B37/B44 de baseline son de layout/canvas, no de física |

**Conclusión:** no hay nada que reutilizar ni reparar. La Fase C construye desde cero
(opciones 4+5 de la libertad técnica: física mínima en bridge/canvas + helpers puros).

## 2. Estado del canvas relevante para física (post-B03)

Infraestructura ya construida en Fase B que la física debe aprovechar, no duplicar:

- **Geometría de anillos reactiva**: `_layout_concentric_rings` (radios desde tamaños
  reales medidos) y `_refresh_ring_spans` (bandas que envuelven contenido sin recolocar).
  `_RingVisual` ya expone `inner_radius`/`outer_radius` por anillo.
- **Pertenencia**: `_node_ring_ids` (nodo→anillo por capa) y `_membership`
  (entity→rama por `contiene`).
- **Jerarquía Qt**: hijos anidados son Qt-children de su `GraphTreeItem`
  (`add_child_node`); mover la rama mueve el contenido automáticamente.
- **Aristas que siguen items**: `_connected_edges` + `ItemSendsScenePositionChanges`
  (incluye hijos cuando se mueve el ancestro) + `_update_attached_edges` en refits.
- **Drag**: `_moving_item`/`_handle_move_drop` (mover, asignar por drop, extraer
  arrastrando fuera); `_space_pan_active` (paneo).
- **Cámara preservada** en rebuilds del mismo layout (`_view_state_to_restore`).

### Coordenadas y parenting (punto 9-10 de la auditoría)

- Items top-level: coordenadas de **escena** (pos = scene pos).
- Hijos anidados: coordenadas **locales del padre**. `setPos` sobre un hijo es local.
- **Contrato derivado**: la física simula SOLO items top-level (hoja suelta o rama
  contenedora como un único cuerpo). El contenido anidado viaja con su rama vía Qt
  y NUNCA se simula individualmente. Esto resuelve de raíz el caso crítico
  "muelle externo expulsa a hijo de su anillo": el hijo no recibe fuerzas.

## 3. Arquitectura elegida

```text
packages/ui/graph_physics/          ← módulos PUROS (sin Qt, testeables headless)
├── __init__.py
├── engine.py        PhysicsEngine: muelles + repulsión + constraint radial,
│                    damping, energía, auto-stop. step(dt) determinista.
├── rings.py         RingBand (inner/outer/target_radius), clamp radial suave,
│                    resolve_effective_ring_id (regla de herencia)
└── invariants.py    ConcentricInvariantChecker (helper puro para tests y QA)

hosts/DesktopHostPySide/widgets/graph_canvas.py   ← bridge mínimo
- _physics_enabled: bool (independiente; persiste en ctx como preferencia)
- QTimer (~30 Hz) → empaqueta cuerpos top-level → engine.step → aplica setPos
- pausa automática durante _moving_item, _space_pan_active y rebuilds
- _refresh_ring_spans() periódico (no por frame) para anillos reactivos
```

Se mantiene: todo lo de Fase B. Se recorta: nada (no hay nada previo).
No se introduce: JS/WebView, GPU/3D, dependencia nueva (NetworkX no es necesario
para simular; matemática pura con `math`).

## 4. Contratos

### 4.1 Flags

```text
_layout_mode ∈ {free, layered, concentric_rings}   (sin cambios)
_physics_enabled ∈ {True, False}                    (nuevo, ortogonal)
```

- El toggle escribe EXCLUSIVAMENTE `_physics_enabled`.
- `set_graph`/cambio de layout no tocan `_physics_enabled` (solo re-empaquetan cuerpos).
- La física jamás escribe `_layout_mode`. Prohibido `"concentric_physics"`.
- Combinaciones: free+ON (repulsión+muelles+compactación suave),
  concentric+ON (constraint radial domina, compactación nula), ambos+OFF (estático).

### 4.2 Anillo efectivo — `resolve_effective_ring_id(item)` (en rings.py)

```text
hoja:  capa explícita → su anillo
       sin capa y dentro de rama con anillo → hereda rama
       sin nada → "__unclassified__" (banda exterior)
rama:  capa explícita → su anillo; sin capa → "__unclassified__"
hijo:  capa explícita → conserva la suya (informativo; NO se simula aparte)
       sin capa → hereda rama
```

Entradas: `_node_ring_ids`, `_membership`, capas del proyecto. Centralizado y puro.
Cambiar el anillo de una rama mueve a los heredados (viajan con ella); los hijos con
capa explícita conservan la suya en datos, pero visualmente permanecen dentro de la
rama mientras pertenezcan a ella (la pertenencia a rama es más fuerte visualmente,
contrato B03 de anidado).

### 4.3 Anillos como campos

- Cada anillo = `RingBand(inner, outer, target_radius=(inner+outer)/2)`.
- Fuerza radial hacia `target_radius` proporcional a la desviación; clamp duro solo
  si el cuerpo sale de `[inner+margen, outer−margen]` (resorte de retorno, no teleport,
  para evitar jitter).
- Sin anillo → banda exterior "__unclassified__". Nadie colapsa al centro:
  la compactación central en concéntrico es 0.
- Los anillos crecen con el mecanismo B03 existente (`_refresh_ring_spans`),
  invocado de forma throttled (p. ej. al estabilizarse la energía), nunca por frame.

### 4.4 Prioridad de fuerzas

```text
1. corona radial (anillo efectivo)   ← gana siempre en concéntrico
2. jerarquía rama/hijo               ← resuelta por parenting Qt, no por fuerzas
3. muelle de relación                ← intra-anillo: normal; inter-anillo: fuerza
                                       reducida y longitud ideal adaptada
4. repulsión entre cuerpos top-level
5. compactación central              ← solo en free
6. inercia/damping
```

### 4.5 Drag/drop

- Press sobre item ⇒ cuerpo **pinned** (la física lo ignora; el resto sigue).
- Durante drag: sin recálculo de layout, ring layout intacto, aristas siguen
  (mecanismo B03 ya existente).
- Release ⇒ unpin SIEMPRE (ningún pin permanente) + retorno suave a su corona si
  quedó fuera, salvo acción explícita:
  - drop sobre rama ⇒ asignación (ruta B03 existente);
  - drop fuera de su rama ⇒ extracción (ruta B03 existente);
  - cambio de anillo SOLO por menú "Mover a anillo" (ruta B03) o, si C04 lo
    decide, drop explícito sobre otro anillo con confirmación de intención.
- La física nunca persiste posiciones ni muta canon (capas/ramas/relaciones solo
  por controladores).

### 4.6 Relaciones

- Muelle con longitud ideal según pareja intra/inter-anillo.
- Inter-anillo: factor de fuerza ≤ 0.3× y longitud ideal ≈ distancia entre
  target_radius de ambos anillos (el muelle acomoda el ángulo, no el radio).
- Tras cada paso: constraint radial re-gana (orden de aplicación en engine.step).

### 4.7 Estabilidad y rendimiento

- Damping ≥ 0.85/paso; auto-stop cuando energía total < umbral (timer se detiene
  hasta reheat por: toggle ON, CRUD, drop, cambio de layout).
- Sin trabajo caro por frame: solo setPos de cuerpos top-level (las aristas se
  actualizan vía itemChange ya existente); spans de anillo throttled.
- Presupuesto C05: fluido a 10/25, usable a 50 cuerpos top-level. Si se supera,
  damping agresivo + menor frecuencia (modo simplificado).

## 5. Riesgos

1. **`setPos` por tick dispara `itemChange`→`update_path` por arista**: con muchos
   edges puede ser el cuello. Mitigación: batch — durante el tick, suprimir
   updates por item y hacer una pasada única de `update_path` al final del frame.
2. **Lucha clamp↔muelle (jitter)**: mitigado por fuerza inter-anillo reducida y
   clamp como resorte; invariante "sin NaN/inf" en checker.
3. **Reescalado de anillos durante simulación**: cambiar radios mientras la física
   corre puede oscilar. Mitigación: spans solo en estados de baja energía.
4. **Items movidos manualmente** (B03 permite colocación libre): la física ON los
   recolocará hacia su corona — es el contrato (la colocación manual fina es para
   física OFF). Documentar en UI/ayuda.
5. **Fallos B37/B44 preexistentes**: son de layout estático; C03 puede de hecho
   arreglar `test_b44_concentric_layout_places_items_inside_their_ring` al
   introducir el constraint radial. Si ocurre, se documenta como arreglo legítimo.

## 6. Brechas de test y plan

Tests existentes de física: **ninguno**. Brecha total, a cubrir por fase:

- C02 → `tests/desktop/test_beta1_physics_toggle.py` (flag, timer, independencia
  de layout, ausencia de "concentric_physics" por grep estático).
- C03 → `tests/desktop/test_beta1_ring_clamp.py` (corona, huérfanos al exterior,
  inter-anillo, expansión, gap, NaN) — mayormente sobre los módulos puros.
- C04 → `tests/desktop/test_beta1_drag_physics.py` (pin/unpin, retorno, herencia
  de anillo en ramas, hijos explícitos, aristas).
- C05 → `docs/cierres/C05_physics_smoke.md` (manual + perf 10/25/50).

Plan C02-C05: sin ajustes de alcance respecto al enunciado de fase; único cambio
de supuesto: **todo se construye nuevo** (no hay motor que reparar), con los módulos
puros primero (C03 testeable sin Qt) y el bridge mínimo en C02.

## 7. Veredicto C01

**PASS** — auditoría completa, decisión de arquitectura tomada (construcción nueva
mínima: módulos puros + bridge), contratos definidos y verificables, sin
contradicciones con el código real.
