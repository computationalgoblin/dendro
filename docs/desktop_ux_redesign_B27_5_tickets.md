# B27.5 — Rediseño UX Desktop App

Estado: APROBADO PARA IMPLEMENTAR — primer lote T01 + T02 + T06 + T07
Fecha: 2026-06-01
Ámbito: `hosts/DesktopHostPySide/`
Perfil principal: UI/UX Agent
Skills obligatorias al implementar cada ticket: `narrative-architect-agents` + `na-ui-agent`.

## Contexto

La UI actual permite acceder a parte del backend, pero se percibe como una herramienta técnica de administración: tablas densas, IDs visibles, JSON/metadata crudos, inspectores saturados, ventanas nuevas y poca intención UX.

B27.5 rediseña la Desktop App como producto local de creación narrativa: navegación minimalista, grafo central, galería estética, workspace de sesión y modo avanzado para datos técnicos.

## Principios obligatorios

1. No eliminar funcionalidad conectada: reubicarla.
2. No crear modelos paralelos en UI.
3. La UI llama a controllers/services reales.
4. El grafo es vista interactiva sobre entidades/relaciones existentes; no es base de datos.
5. IA no modifica canon directamente; produce sugerencias/candidatos.
6. En modo normal no se muestran IDs, JSON, metadata raw, custom fields técnicos, listas tipo Python ni nombres internos de clases.
7. Datos técnicos solo en modo avanzado/debug.
8. Validación final requiere smoke manual Windows real, no solo compileall/pytest arquitectura.
9. Modo normal nunca muestra IDs, pero debe permitir copiar una referencia humana limpia cuando sea útil: por ejemplo `Aria · Personaje` o `Campaña B27.4 / Sesión 1`. Los IDs solo aparecen en “Datos técnicos” con modo avanzado activo.

## UX objetivo

Shell:

- Sidebar izquierda minimalista.
- Solo tres entradas principales:
  - Creación
  - Galería
  - Sesión
- Configuración abajo en sidebar:
  - Abrir proyecto
  - Guardar proyecto
  - Cerrar proyecto
  - Ajustes IA
  - Modo avanzado
  - Diagnóstico
- Sin Dashboard como pantalla principal.
- Zona central dinámica.
- Panel derecho contextual limpio y opcional.
- Log técnico oculto por defecto.

Workspaces:

- Creación: entrada principal por grafo narrativo.
- Galería: cards tipo Notion/mural/lista limpia.
- Sesión: campañas, sesiones, facciones, frentes, clocks, secretos, pistas, live y post-session.

## Tickets

---

## B27.5-T01 — UX Shell redesign

Perfil: ui-agent
Prioridad: P0
Dependencias: ninguna

### Objetivo

Rediseñar el shell principal para eliminar el Dashboard técnico y dejar una navegación minimalista de producto con tres espacios principales: Creación, Galería y Sesión. Mover proyecto/configuración a la zona inferior del sidebar.

### Alcance

- Eliminar Dashboard como pantalla inicial visible.
- Sidebar principal con solo:
  - Creación
  - Galería
  - Sesión
- Zona inferior de sidebar con Proyecto/Configuración:
  - Abrir proyecto
  - Guardar proyecto
  - Cerrar proyecto
  - Ajustes IA
  - Modo avanzado
  - Diagnóstico
- Topbar limpia con estado discreto:
  - proyecto abierto/cerrado
  - guardado pendiente si aplica
  - provider/model IA resumido si aplica
- Log técnico oculto por defecto.
- Mantener acceso a funcionalidades existentes reubicadas dentro de workspaces o modo avanzado.

### No hacer

- No borrar servicios/controllers existentes.
- No crear lógica paralela de proyecto.
- No mostrar IDs ni datos técnicos en el shell normal.

### Criterios de aceptación

- Al abrir la app no aparece Dashboard técnico.
- Sidebar visible solo muestra Creación, Galería y Sesión como navegación principal.
- Abrir/Guardar/Cerrar proyecto están en configuración inferior.
- El log técnico no ocupa espacio visible por defecto.
- La app sigue pudiendo abrir, guardar y cerrar proyectos.
- No se pierde ninguna pantalla existente: queda reubicada o accesible en modo avanzado.

### Prueba manual Windows

1. Ejecutar app desde Windows.
2. Confirmar que no aparece Dashboard técnico.
3. Confirmar sidebar: Creación, Galería, Sesión.
4. Abrir un proyecto desde Configuración.
5. Guardar proyecto desde Configuración.
6. Cerrar proyecto desde Configuración.
7. Reabrir el proyecto.
8. Confirmar que no se ven IDs/JSON en el shell normal.

---

## B27.5-T02 — Design system / theme minimalista

Perfil: ui-agent
Prioridad: P0
Dependencias: B27.5-T01

### Objetivo

Crear un sistema visual coherente, minimalista y estético para abandonar la apariencia de CRUD técnico.

### Alcance

- Theme base para PySide:
  - espaciado consistente
  - cards con bordes suaves
  - chips/badges para estado/categoría
  - botones con jerarquía clara
  - tipografía consistente
  - colores discretos por categoría
- Componentes reutilizables:
  - Card
  - Chip/Badge
  - EmptyState
  - SectionHeader
  - CleanListItem
  - AdvancedSection colapsable
- Estados visuales:
  - activo
  - borrador
  - canon/no canon
  - oculto/revelado
  - pendiente/aceptado/rechazado
- Reducir tablas densas en modo normal.

### No hacer

- No convertir la app en web app.
- No introducir framework externo innecesario.
- No ocultar errores funcionales detrás de estilos.

### Criterios de aceptación

- Las pantallas nuevas usan cards/chips/espaciado común.
- Los estados se ven como badges humanos, no enums crudos.
- Las tablas densas quedan relegadas a modo avanzado o vistas secundarias.
- No hay listas tipo Python ni JSON en modo normal.

### Prueba manual Windows

1. Abrir app.
2. Navegar a Creación, Galería y Sesión.
3. Confirmar estilo visual consistente.
4. Confirmar que cards/chips sustituyen tablas técnicas donde aplique.
5. Confirmar que estados aparecen en lenguaje humano.

---

## B27.5-T03 — Graph-first Creation workspace

Perfil: ui-agent + graph-agent si se divide
Prioridad: P0
Dependencias: B27.5-T01, B27.5-T02

### Objetivo

Sustituir Corpus/Relaciones como entrada principal por un workspace de Creación centrado en un grafo interactivo de entidades y relaciones.

### Alcance

- Workspace Creación abre por defecto en grafo narrativo.
- Nodos visibles por tipo humano.
- Aristas visibles con etiqueta limpia.
- Crear nodo desde el grafo.
- Crear relación desde el grafo.
- Click nodo → panel derecho contextual limpio.
- Doble click nodo → foco/zoom o selección ampliada, no ventana nueva.
- Filtro por tipo.
- Drag/reorganización visual si PySide lo permite.
- Botones:
  - + Nodo
  - + Relación
  - Sugerir con IA
- Buscador/filtro.
- Filtros por tipo/capa/domain si existen.
- Corpus técnico y tablas quedan como subvista avanzada/secundaria.

### Panel de nodo en modo normal

Mostrar:

- Nombre
- Tipo en lenguaje humano
- Descripción
- Estado canon/visibilidad humano
- Relaciones importantes por nombre
- Apariciones/escenas/campañas vinculadas si existen
- Notas
- Acciones:
  - Editar
  - Relacionar
  - Crear pista/secreto
  - Pedir sugerencia IA
  - Ver detalles avanzados

No mostrar por defecto:

- ID
- JSON
- metadata raw
- source_ids crudos
- custom fields técnicos
- arrays internos

### Panel de relación en modo normal

Mostrar:

- Origen por nombre
- Destino por nombre
- Tipo en lenguaje natural
- Descripción
- Intensidad/estado si existe
- Notas
- Editar
- Archivar/eliminar si servicio lo permite

### Criterios de aceptación

- Creación empieza por grafo, no tabla corpus.
- El usuario puede crear un nodo desde el grafo.
- El usuario puede crear una relación desde el grafo.
- Click en nodo muestra inspector limpio lateral, sin ventana nueva.
- Doble click enfoca/zoom, no abre QDialog técnico.
- No se ven IDs en modo normal.
- Corpus/Relation CRUD técnico queda accesible solo como avanzado/secundario.

### Prueba manual Windows

1. Abrir proyecto.
2. Entrar en Creación.
3. Crear personaje desde botón + Nodo.
4. Crear localización desde botón + Nodo.
5. Relacionar personaje-localización desde + Relación o gesto del grafo.
6. Click en personaje: ver panel limpio sin ID.
7. Doble click: enfoca/zoom, no ventana nueva.
8. Guardar/cerrar/reabrir y confirmar que nodo y relación persisten.

---

## B27.5-T04 — Gallery workspace

Perfil: ui-agent
Prioridad: P1
Dependencias: B27.5-T01, B27.5-T02

### Objetivo

Crear una Galería estética tipo Notion para visualizar datos ya ingresados sin apariencia de tabla técnica.

### Alcance

- Workspace Galería con cards.
- Cards de:
  - entidades
  - facciones
  - localizaciones
  - campañas
  - sesiones
  - secretos/pistas si modo GM lo permite
- Buscador.
- Filtros visuales por tipo/dominio/capa/campaña/sesión.
- Agrupaciones por tipo, dominio, capa, campaña o sesión.
- Modos:
  - tarjetas
  - mural
  - lista limpia
  - timeline si aplica
  - grafo si aplica
- Click card → panel lateral limpio o vista detalle estética.

### Card de entidad

Mostrar:

- Nombre
- Tipo con icono/color
- Descripción breve
- Relaciones destacadas
- Apariciones
- Estado visual
- Imagen/placeholder/icono si existe

No mostrar:

- ID
- JSON
- metadata
- listas técnicas

### Criterios de aceptación

- Galería muestra cards limpias, no tabla Excel.
- Buscar/filtrar funciona.
- Click en card abre detalle limpio.
- No se ven IDs/JSON/metadata en modo normal.
- Datos técnicos solo aparecen en avanzado.

### Prueba manual Windows

1. Abrir proyecto con varias entidades/campañas/sesiones.
2. Entrar en Galería.
3. Confirmar cards visibles.
4. Filtrar por tipo.
5. Buscar una entidad por nombre.
6. Abrir detalle de card.
7. Confirmar que no hay IDs/JSON en modo normal.

---

## B27.5-T05 — Session workspace visual completo

Perfil: ui-agent + rpg-agent si se divide
Prioridad: P0
Dependencias: B27.5-T01, B27.5-T02

### Objetivo

Unificar campañas, sesiones, facciones, frentes, clocks, secretos, pistas, live y post-session en un flujo visual de rol usable.

### Alcance

Pantalla principal de Sesión dividida visualmente en tres subzonas para evitar saturación:

- Campaña.
- Preparación.
- En vivo/Post.

Subzona Campaña:

- Formulario limpio completo:
  - nombre
  - mundo
  - sistema
  - tono
  - género
  - estado
  - descripción
  - notas privadas
  - resumen público
- Players y clocks visibles inmediatamente tras añadirse.

Facciones/fronts/clocks:

- Faction cards.
- Objetivos editables.
- Ideología/métodos/recursos/líderes/miembros si existen.
- Fronts visibles.
- Stages visibles como timeline/stepper.
- Clocks como barras de progreso accionables.

Sesiones/escenas:

- Crear sesión vinculada a campaña.
- Scene cards con:
  - título
  - contexto
  - objetivo
  - entidades
  - pistas
  - secretos
  - facciones
  - clocks
  - notas GM
  - resumen visible jugadores
- Reordenar si servicio lo permite.

Live/Post:

- Quick note editable con texto completo.
- Decision/event/consequence.
- Reveal secret selector real.
- Deliver clue selector real.
- Improvise IA con error humano si falla.
- Close session.
- Post summaries.
- Convert live notes to candidates idempotente.

### Criterios de aceptación

- Sesión no es colección de tabs técnicas, sino flujo visual.
- Campaña se puede crear/editar con campos principales.
- Players/clocks añadidos se ven inmediatamente.
- Facciones tienen objetivos visibles/editables.
- Front stages visibles y editables.
- Escenas tienen contenido/contexto real, no solo nombre.
- Live/Post es usable con texto completo.
- No se ven IDs/JSON en modo normal.

### Prueba manual Windows

1. Entrar en Sesión.
2. Crear campaña con mundo/sistema/tono/género/estado.
3. Añadir player y clock; confirmar que aparecen inmediatamente.
4. Crear facción con objetivos.
5. Crear front con stages; ver stepper/timeline.
6. Crear sesión vinculada a campaña.
7. Crear escena con contexto, objetivo y notas GM.
8. Iniciar live mode, añadir quick note/decision/event/consequence.
9. Cerrar sesión y generar post summaries/candidates.
10. Guardar/cerrar/reabrir y confirmar persistencia.

---

## B27.5-T06 — Advanced mode / debug mode

Perfil: ui-agent
Prioridad: P0
Dependencias: B27.5-T01, B27.5-T02

### Objetivo

Separar completamente experiencia normal de datos técnicos. IDs, JSON, metadata, custom fields y logs solo deben verse en modo avanzado/debug.

### Alcance

- Toggle “Modo avanzado” en Configuración.
- Estado global en AppContext o equivalente.
- En modo normal ocultar:
  - IDs
  - JSON
  - metadata raw
  - custom fields técnicos
  - source_ids crudos
  - listas tipo Python
  - nombres de clases internas
  - tracebacks
- En modo avanzado mostrar sección colapsada “Datos técnicos”.
- Panel Debug/Diagnóstico con logs/tracebacks si avanzado activo.
- Errores de usuario se muestran en lenguaje humano.

### Criterios de aceptación

- Modo normal no muestra datos técnicos.
- Modo avanzado muestra datos técnicos bajo secciones claramente marcadas.
- El log técnico está oculto por defecto.
- Las excepciones no aparecen como traceback en pantalla principal.

### Prueba manual Windows

1. Abrir app en modo normal.
2. Revisar Creación/Galería/Sesión: no IDs/JSON/metadata.
3. Activar Modo avanzado en Configuración.
4. Abrir detalle de entidad/relación/import candidate.
5. Confirmar sección “Datos técnicos”.
6. Desactivar modo avanzado y confirmar que desaparece.

---

## B27.5-T07 — Import UX as cards

Perfil: ui-agent + import-agent si se divide
Prioridad: P0
Dependencias: B27.5-T02, B27.5-T06

### Objetivo

Rehacer la importación documental como flujo visual de cards, corrigiendo definitivamente `basket.candidates` y evitando tabla técnica.

### Alcance

Flujo:

1. Seleccionar documento.
2. Ver resumen de segmentos detectados.
3. Ver baskets como cards.
4. Ver candidates como cards.
5. Aceptar/Rechazar/Editar como acciones de card.

Candidate card:

- “Posible personaje: Aria” / tipo humano.
- Confianza visual.
- Texto fuente breve.
- Acciones:
  - aceptar
  - editar
  - descartar
  - merge/partial si servicio existe

Obligatorio técnico:

- Buscar/corregir cualquier uso de `basket.candidates`.
- Modelo real: `basket.import_candidates`.
- Usar compat defensiva:
  - `items = getattr(basket, "import_candidates", [])`
- Añadir regression test/smoke específico de ImportBasket UI rows/cards.

No mostrar en modo normal:

- `ImportCandidate`
- `segment_id`
- `basket_id`
- IDs internos
- JSON/proposed_data crudo

### Criterios de aceptación

- Importar `.txt` crea basket sin crash.
- Refresh no falla por `basket.candidates`.
- Basket aparece inmediatamente como card.
- Candidates aparecen como cards.
- Aceptar/rechazar/editar funciona si servicio lo permite.
- Datos técnicos solo en avanzado.

### Prueba manual Windows

1. Abrir proyecto.
2. Entrar en Creación → Importación.
3. Importar `.txt`.
4. Confirmar que aparece basket card.
5. Abrir candidates como cards.
6. Aceptar un candidate.
7. Rechazar otro candidate.
8. Guardar/cerrar/reabrir.
9. Confirmar que no reaparece crash `ImportBasket has no attribute candidates`.

---

## B27.5-T08 — AI contextual UX / OpenCode Zen diagnostics

Perfil: ui-agent + ai-agent si se divide
Prioridad: P0
Dependencias: B27.5-T01, B27.5-T03, B27.5-T06

### Objetivo

Empezar por diagnóstico claro del provider IA antes de añadir nuevas acciones contextuales. Integrar después IA contextual en flujos de creación y mostrar errores humanos/diagnósticos útiles, especialmente 403 Forbidden de OpenCode Zen/OpenAI-compatible.

### Primer entregable obligatorio

La app debe mostrar en Ajustes IA/Diagnóstico:

```text
Provider: openai_compatible
Base URL: https://opencode.ai/zen/v1
Model: ...
Auth: configurada
Test: 403 Forbidden — revisa key/modelo/permisos
```

Nunca mostrar API key.

### Alcance

IA contextual desde:

- grafo
- nodo/entidad
- relación
- escena
- facción/front
- import candidate

Acciones IA:

- sugerir entidad relacionada
- sugerir relación
- expandir descripción
- detectar contradicciones
- resumir nodo
- improvisar en sesión

Diagnóstico provider:

- En Configuración/Ajustes IA mostrar:
  - provider
  - base_url saneada
  - model
  - auth present: yes/no
  - nunca API key
- Test provider con respuesta humana.
- Si HTTP 403:
  - “La IA respondió 403 Forbidden. Revisa API key, modelo o permisos.”
  - mostrar body resumido si existe, sin secretos.
- Distinguir:
  - credenciales/config inválida
  - bug UI/provider factory
  - endpoint/model incorrecto

### Criterios de aceptación

- No hay fallback simulated silencioso.
- El usuario entiende si la IA falló por 403.
- Provider/model/base_url se ven en ajustes, no invaden UI normal.
- Ninguna API key aparece en logs/UI.
- Sugerir con IA está disponible desde grafo/nodo/escena/facción.

### Prueba manual Windows

1. Configurar OpenCode Zen env vars.
2. Abrir Ajustes IA.
3. Confirmar provider/base_url/model/auth present.
4. Ejecutar Test provider.
5. Si 403, confirmar mensaje humano y sin API key.
6. Desde Creación, seleccionar nodo y pedir sugerencia IA.
7. Confirmar candidate/sugerencia o error humano.

---

## B27.5-T09 — Windows manual smoke validation

Perfil: qa-agent
Prioridad: P0
Dependencias: B27.5-T01..T08

### Objetivo

Crear y ejecutar un smoke manual Windows específico para B27.5 que valide UX real, persistencia y ausencia de datos técnicos visibles.

### Alcance

- Script/checklist Windows para validación manual.
- No basta compileall + architecture.
- Debe cubrir el flujo completo esperado por usuario.

### Checklist manual esperado

1. Abrir app.
2. Abrir proyecto desde Configuración.
3. Entrar en Creación.
4. Crear personaje desde grafo.
5. Crear localización desde grafo.
6. Relacionarlos visualmente.
7. Pedir sugerencia IA.
8. Ver entidades en Galería como cards.
9. Crear campaña en Sesión con tono/género/mundo.
10. Crear facción con objetivos.
11. Crear front con stages.
12. Crear sesión con escenas completas.
13. Importar documento y revisar candidatos como cards.
14. Guardar/cerrar/reabrir.
15. Confirmar persistencia.
16. Confirmar que en modo normal no se ven IDs/JSON/metadata.
17. Activar modo avanzado y confirmar que los datos técnicos aparecen solo ahí.

### Criterios de aceptación

- Checklist ejecutado en Windows real.
- Outputs/logs reales adjuntos al cierre.
- Bugs encontrados se convierten en tickets o bloquean cierre.
- No cerrar B27.5 sin validación visual/manual del usuario.

---

## Orden sugerido de implementación

1. B27.5-T01 — Shell redesign.
2. B27.5-T02 — Design system.
3. B27.5-T06 — Advanced/debug mode.
4. B27.5-T07 — Import cards + fix P0 `import_candidates`.
5. B27.5-T03 — Graph-first Creation.
6. B27.5-T04 — Gallery workspace.
7. B27.5-T05 — Session workspace.
8. B27.5-T08 — AI contextual UX.
9. B27.5-T09 — Windows smoke validation.

## Validaciones técnicas mínimas por ticket

Cada ticket implementado debe ejecutar, como mínimo:

- `python -m compileall hosts/DesktopHostPySide -q`
- `python -m pytest tests/architecture/ -q`
- tests específicos del ticket
- smoke de instanciación `MainWindow` con `QT_QPA_PLATFORM=offscreen` si PySide6 disponible
- prueba manual Windows específica indicada en el ticket

## Criterio de cierre B27.5

B27.5 solo puede cerrarse cuando:

- T01..T09 están completos.
- El usuario valida manualmente en Windows.
- La UI normal no muestra datos técnicos.
- Creación empieza por grafo.
- Galería usa cards limpias.
- Sesión es un flujo visual usable.
- Import usa cards y no crashea.
- IA muestra diagnóstico humano.
- La persistencia guardar/cerrar/reabrir conserva todo lo creado.
