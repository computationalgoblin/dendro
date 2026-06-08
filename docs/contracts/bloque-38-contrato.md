# Bloque 38 — Command Bar IA y reorganización de Creación

## Estado

Aprobado, implementado y cerrado documentalmente. Ver `docs/cierres/bloque-38-cierre.md`.

## Contexto

B33-B37 han estabilizado Creación como superficie principal de trabajo narrativo:

- B33: nodos, relaciones, IA inline y persistencia.
- B34: árboles, jerarquía y contexto IA.
- B35: coherencia de subgrafo y reparación revisable.
- B36: capas causales de worldbuilding.
- B37: búsqueda, filtros, foco, cámara, bandeja de sugerencias y smoke de proyecto mediano.

B38 reorganiza la interfaz principal y añade una consola IA contextual capaz de lanzar tareas sobre el grafo sin bloquear la UI y sin canonizar automáticamente.

## Objetivo

1. Reorganizar la superficie de Creación.
2. Sustituir la barra inferior de botones por una barra superior organizada.
3. Convertir el panel de capas en un drawer persistente con botón propio.
4. Reservar la parte inferior central para una command bar IA.
5. Introducir un contrato de AI Jobs no bloqueantes.
6. Ejecutar los primeros jobs MVP como resultados revisables.
7. Conectar resultados estructurales a la bandeja de sugerencias/candidatos.

## Nueva disposición UX

```text
┌────────────────────────────────────────────────────────────┐
│ +  ▣  ↔  ✨  ⚠  ⌕  ◌  ⊹        Importar | Vista | Fit | Reset │
├───────┐                                                    │
│ Capas │                                                    │
│       │                    GRAFO                           │
│       │                                                    │
│       │          [ Pídele a Dendro...              ↵ ]      │
└───────┴────────────────────────────────────────────────────┘
```

### Zonas

- Arriba izquierda: acciones creativas sobre el grafo.
- Arriba derecha: herramientas secundarias/gestión.
- Izquierda: panel persistente de capas worldbuilding.
- Abajo centro: command bar IA contextual.
- Centro: grafo, sin reescritura del canvas.

## Reglas obligatorias

1. La IA nunca modifica canon directamente.
2. Todo resultado estructural de IA queda como candidato/sugerencia revisable.
3. La UI no escribe directamente en persistencia.
4. No se crean modelos paralelos si `Candidate`, `AIContextActions`, `GraphCanvasWidget` o servicios existentes ya cubren el concepto.
5. No se abren ventanas externas.
6. No se muestran IDs/JSON en modo normal.
7. Los filtros/vistas son visuales y efímeros salvo contrato explícito posterior.
8. La app debe seguir funcionando sin IA configurada.
9. Las tareas IA largas no bloquean la UI.
10. B38 no toca Galería ni Sesión.

## Alcance incluido

### Reorganización UI

- Mover botones principales de Creación a parte superior izquierda:
  - crear entidad
  - crear árbol
  - crear relación / modo conexión
  - sugerir
  - coherencia
  - buscar
  - filtros
  - bandeja de sugerencias
- Mover herramientas secundarias a parte superior derecha:
  - importar documento
  - vista libre/capas
  - fit all
  - reset
  - exportar vista si ya existe API viable
- Eliminar barra inferior de botones actual.
- Añadir command bar inferior central.

### Panel izquierdo de capas

- Botón fijo para abrir/cerrar.
- Persistente hasta volver a pulsar.
- No depende de hover.
- Si Worldbuilding OFF, ocultar o deshabilitar con explicación.
- Mostrar:
  - lista de capas
  - capa activa
  - contadores de elementos por capa si existen o pueden derivarse del grafo cargado
  - acción enfocar/filtrar capa
  - acción ocultar/mostrar capa si ya existe API visual suficiente
- No edición avanzada de capas en B38.

### Command bar IA

- Placeholder: `Pídele a Dendro que actúe sobre el grafo…`
- Enter lanza job.
- Shift+Enter permite salto de línea si se usa widget multilínea; si el MVP usa línea única, documentar limitación.
- Usa contexto actual:
  - proyecto
  - configuración creativa
  - worldbuilding ON/OFF
  - selección actual
  - filtros activos
  - árbol enfocado
  - capa activa
  - vista actual
- No llama IA directamente desde UI sin pasar por job layer.

### AI Jobs MVP

Estados:

- queued
- building_context
- running
- postprocessing
- ready_for_review
- failed
- cancelled

Tipos MVP:

- generate_entities
- generate_tree
- suggest_relations
- analyze_coherence
- expand_worldbuilding
- explain_from_causes
- review_graph

Campos mínimos:

- id
- type
- prompt
- status
- created_at
- updated_at
- progress/message
- context_scope
- result
- error
- cancellable

Persistencia:

- MVP in-memory permitido.
- Debe documentarse explícitamente como decisión temporal.
- No guardar API keys ni logs sensibles.

### Jobs funcionales iniciales

1. `generate_entities`
   - Prompt ejemplo: “Créame tres personajes para empezar esta historia”.
   - Resultado: candidatos de entidad.
2. `generate_tree`
   - Prompt ejemplo: “Crea un sistema metafísico para empezar el worldbuilding”.
   - Resultado: árbol candidato y, si viable, nodos/relaciones candidatas.
3. `analyze_coherence` / `review_graph`
   - Prompt ejemplo: “Revisa todo el grafo y proponme mejoras”.
   - Resultado: informe + propuestas revisables, sin cambios directos.

## Fuera de alcance

- Galería.
- Sesión.
- Embeddings/cache avanzado.
- Map-reduce avanzado.
- Jobs largos de minutos con persistencia durable.
- Rediseño/rewrite completo del canvas.
- Edge aggregation visual.
- Edición avanzada de capas.
- Edición masiva automática.
- Aplicar cambios al canon sin aceptación.

## Infraestructura existente que debe reutilizarse

Auditoría B38 inicial:

- `hosts/DesktopHostPySide/views/workspaces.py`
  - `CreationWorkspace`
  - `CandidateReviewPanel`
  - `SuggestionInboxPanel`
  - `_LayerEdgeFlyout` / estado visual de capas B37
- `hosts/DesktopHostPySide/widgets/graph_canvas.py`
  - `GraphCanvasWidget`
  - `VisualFilterState`
  - búsqueda/filtros/foco/cámara/capas
- `hosts/DesktopHostPySide/widgets/coherence_panel.py`
  - patrón QThread no bloqueante para coherencia
- `hosts/DesktopHostPySide/widgets/tree_detail_panel.py`
  - patrón QThread para IA contextual de árbol
- `hosts/DesktopHostPySide/controllers/ai_context_controller.py`
  - puente UI → `AIContextActions`
- `packages/application/ai_context_actions.py`
  - acciones IA existentes, coherencia B35, causal B36, graph actions
- `packages/domain/candidate_issue.py`
  - `Candidate` como base de resultados revisables
- `packages/application/candidate_service.py`
  - aceptación/rechazo de candidatos

## Validaciones obligatorias

- `python -m compileall hosts/DesktopHostPySide packages -q`
- `python -m pytest tests/architecture/ -q`
- `python scripts/run_all_tests.py --suites arch desktop infra sanity b33 b34 b35 b36 b37`
- Tests B38 específicos añadidos a `scripts/run_all_tests.py`
- Smoke visual Windows:
  1. Abrir Creación.
  2. Confirmar barra superior nueva.
  3. Confirmar panel capas abre/cierra con botón.
  4. Confirmar command bar inferior.
  5. Prompt generate_entities.
  6. Confirmar job no bloquea UI.
  7. Confirmar candidatos revisables.
  8. Aceptar uno y confirmar nodo real.
  9. Rechazar otro y confirmar que no aparece.
  10. Prompt generate_tree.
  11. Confirmar resultados revisables.
  12. Prompt review_graph.
  13. Confirmar informe sin cambios automáticos.
  14. Confirmar sin ventanas externas.
  15. Confirmar sin IDs/JSON.
  16. Confirmar sin nodos fantasma.

## Orden recomendado

Primera tanda:

- B38-T01 — Reorganización de UI de Creación
- B38-T02 — Panel izquierdo persistente de capas
- B38-T03 — Command bar IA inferior
- B38-T04 — AI Job model/service básico

Segunda tanda:

- B38-T05 — Runner no bloqueante PySide
- B38-T06 — Clasificación de intención y dispatch
- B38-T07 — Resultados a bandeja de sugerencias
- B38-T08 — Primeros jobs funcionales
- B38-T09 — Smoke Windows de command bar

## Definición de terminado del bloque

B38 está terminado solo si:

- La nueva disposición de Creación es visible en Windows.
- El panel de capas no depende de hover.
- La command bar crea jobs, no llamadas IA directas.
- Los jobs no bloquean la UI.
- Los resultados estructurales llegan a revisión/candidatos.
- Aceptar/rechazar usa servicios reales.
- No hay mutación automática de canon.
- Tests B38 y regresiones B33-B37 pasan.
- Se documenta deuda honesta si queda alguna limitación MVP.
