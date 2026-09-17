# BETA1 — Auditoría de limpieza legacy y plan de actuación

> ⛔ **ACTUALIZACIÓN (2026-07-02): la Importación de documentos se RETIRÓ por completo.**
> Este documento describía la Importación como "capacidad central de BETA1"; esa decisión se
> revirtió: el subsistema (canon + reservorio/contexto + germinación + extracción de texto +
> `import_baskets`) se eliminó por inviable. La app ya no acepta documentos. Ignora las líneas
> que marcan Importación como KEEP/central.

Fecha: 2026-06-15
Estado: contrato de limpieza aprobado por entrevista de producto
Alcance: H00/H01 y plan posterior de reducción de código legacy

## 1. Decisión de producto

Dendro BETA1 se redefine como una aplicación centrada en **Creación narrativa / worldbuilding** con **Importación** como capacidad central y con **IA** como protagonista del flujo creativo.

El runtime de producto no debe volver al modelo anterior de suite amplia con espacios separados de campaña, sesión, galería, escritura, frameworks, secretos o live mode. La navegación principal se mantiene como:

```text
Home -> Creación
```

Importación debe estar disponible desde menú/proyecto/configuración, no como un espacio autónomo de producto. La IA está siendo trabajada por otro modelo y queda explícitamente fuera de esta limpieza salvo decisiones de interfaz/documentación.

## 2. Ontología visible objetivo

### 2.1 Hoja

Una **Hoja** es cualquier elemento individual que no puede contener otros elementos.

Tipos visibles iniciales:

- Personaje
- Objeto
- Nota

No deben aparecer como tipos normales de Hoja en BETA1:

- Localización/lugar, porque puede contener otros elementos y debe modelarse como Rama.
- Facción, cultura, religión, sistema mágico, institución, trama o contenedor: deben tratarse como Rama.
- Secreto y pista: salen del producto BETA1.
- Sesión, escena RPG, campaña, front, reloj, framework, escritura: salen del producto BETA1.

Internamente puede seguir existiendo `NarrativeEntity`; la limpieza visible no exige renombrar el core.

### 2.2 Rama

Una **Rama** es un elemento que puede contener otros elementos.

Contrato visible:

- Puede contener Hojas.
- Puede contener otras Ramas.
- Tiene descripción.
- Mantiene la acción **Crear anillo desde rama**.
- No es una carpeta técnica: es una entidad agrupadora de producto.

Internamente puede seguir apoyándose en `EntityType.CONTENEDOR`, `tree_meta.py` y metadatos. No se crea un modelo paralelo de Rama.

### 2.3 Anillo

Un **Anillo** es la forma visible de trabajar con estratos/zonas de mundo en Creación.

Contrato visible:

- Los anillos están siempre disponibles en BETA1.
- Un proyecto nuevo empieza sin anillos preinyectados.
- La UI normal debe decir **Anillo**, nunca `layer` ni `capa`.
- No debe existir una pantalla técnica `LayerView` separada para usuario normal; la gestión de anillos debe ocurrir desde Creación.

Internamente puede seguir existiendo `WorldLayer` y `world_layer_causal.py`.

### 2.4 Relación

La relación visible deja de depender de un catálogo cerrado de `RelationType` legacy. El usuario debe poder definir tipos de relación personalizados.

Contrato objetivo:

- La relación se crea con un nombre/tipo libre o reutilizable.
- Los tipos internos existentes quedan para compatibilidad y migraciones, no como selector principal obligatorio.
- Las relaciones de secreto/conocimiento/RPG no se muestran en BETA1.

### 2.5 Semilla

El concepto visible de **Candidato** pasa a llamarse **Semilla**.

Estado:

- Se mantiene temporalmente para IA e Importación.
- A medio plazo, Semillas y Jobs deben integrarse directamente en el grafo visual.
- Internamente puede seguir existiendo `Candidate`/`CandidateService` hasta que haya migración.

## 3. Lo que NO existe en BETA1

Por decisión de producto, salen del runtime BETA1:

- Visibilidad.
- Secretos.
- Pistas.
- Campañas RPG.
- Preparación de sesiones.
- Live mode.
- Post-session.
- Facciones/frentes como subsistema propio.
- Galería.
- Escritura.
- Frameworks narrativos.
- CLI como producto.
- Issues/incidencias como sistema visible autónomo.

La coherencia narrativa no es una pantalla permanente: es una acción reactiva solicitada por el usuario sobre una selección previa de entidades.

## 4. Principios de limpieza

1. **No tocar IA en esta fase.** Los ficheros de IA están siendo arreglados en paralelo por otro modelo.
2. **No hacer refactor complejo de `graph_canvas.py`.** Solo bugs muy acotados.
3. **No hacer refactor amplio de `workspaces.py` ahora.** Solo retirar clases desconectadas cuando toque.
4. **No borrar campos persistidos sin migración.** Todo lo que esté en `Project` requiere plan de schema.
5. **CLI no cuenta como producto vivo.** Si algo existe solo en CLI, se considera legacy salvo decisión contraria.
6. **Borrados atómicos.** Cada bloque de limpieza debe tener diff pequeño y tests.
7. **Validación fuerte.** El cierre requiere `python scripts/run_all_tests.py` salvo bloqueo documentado.
8. **Compatibilidad razonable, no absoluta.** Los proyectos antiguos importan, pero se aceptan migraciones bien testeadas.

## 5. Clasificación por subsistema

| Subsistema | Estado objetivo | Acción | Riesgo | Notas |
|---|---|---|---:|---|
| Home | KEEP | Mantener Home -> Creación | Bajo | No reactivar galería/sesión |
| Creación | KEEP | Núcleo de producto | Bajo | No refactor amplio todavía |
| Hojas / `NarrativeEntity` | KEEP | Mantener core, simplificar tipos visibles | Medio | Visible: personaje, objeto, nota |
| Ramas / árboles | KEEP | Mantener contención, nesting y crear anillo desde rama | Medio | Descripción sí; no sobrecargar UI |
| Anillos / `WorldLayer` | KEEP | Mostrar siempre como Anillo | Medio | Quitar lenguaje `layer/capa` visible |
| Relaciones | MIGRATE | Pasar a tipos personalizados visibles | Medio/Alto | `RelationType` queda compatibilidad |
| Semillas / candidatos | TEMPORAL KEEP | Renombrar visible Candidato -> Semilla | Medio | Se retirará como bandeja separada más adelante |
| Importación | ~~KEEP~~ **RETIRADO** | Subsistema eliminado (2026-07-02) | — | Ver BETA1-CLEANUP-IMPORT; la app ya no acepta documentos |
| IA | FREEZE | No tocar en este bloque | Alto | Otro modelo trabaja esta capa |
| Cronología | KEEP | Mantener `ProjectChronology` y `CausalMilestone`; `TimelineEvent` UI retirada | Medio | `TimelineEvent` queda como legacy persistido |
| Visibilidad | REMOVE-LATER | Quitar de UI primero; migrar después | Alto | Muy cruzado con dominio/export/RAG/canvas |
| Secretos/Pistas | REMOVE-LATER | UI normal retirada; migrar/eliminar después | Alto | No hay secretos en producto |
| Campaña/Sesiones/Live/Post | REMOVE | UI/controladores Desktop retirados; dominio con migración posterior | Alto | No son BETA1 |
| Facciones/Frentes | REMOVE-LATER | UI normal retirada; Facción = Rama; front/reloj fuera | Alto | Requiere migración si se borra dominio |
| Galería | DELETE | Borrar workspace legacy | Medio | No vuelve como espacio |
| Escritura | REMOVE-LATER | Sacar de producto; migrar después si procede | Medio/Alto | No es BETA1 |
| Frameworks | REMOVE-LATER | Sacar de producto | Medio | No visible ni herramienta |
| CLI | LEGACY | No usar como criterio de vida | Medio | Borrar comandos al borrar subsistema |
| Diagnóstico/mantenimiento | INTERNAL | Mantener solo si ayuda QA/dev | Bajo/Medio | No UI normal |

## 6. Estado actual relevante del código

### 6.1 Runtime Desktop

`hosts/DesktopHostPySide/main_window.py` ya declara que BETA1 solo instancia Home y Creación. `docs/architecture/A03_legacy_classification.md` clasifica explícitamente vistas/controladores desconectados.

Runtime vivo:

- `HomeView`
- `CreationWorkspace`
- paneles de Creación
- canvas/grafo/física
- importación dentro del ecosistema de Creación

Desconectado según A03:

- `GalleryWorkspace`
- `SessionWorkspace`
- `SessionPreparationWorkspace`
- `SessionOverview`
- `CampaignView`
- `SessionView`
- `LivePostView`
- `IssuesHistoryView`
- controladores `issue`, `live_mode`, `post_session`, `campaign`, `session`, `secrets`, `faction`, `timeline`

### 6.2 Persistencia

`Project` todavía conserva muchas colecciones históricas:

- `entities`
- `relations`
- `sources`
- `history`
- `issues`
- `narrative_frameworks`
- `framework_templates`
- `timeline_events`
- `candidates`
- `world_layers`
- `import_baskets`
- `writing_units`
- `campaigns`
- `player_character_profiles`
- `campaign_clocks`
- `secrets`
- `clues`
- `factions`
- `fronts`
- `sessions`
- `saved_graph_views`
- `causal_milestones`
- `project_chronology`

Regla: las colecciones fuera de producto no se borran físicamente sin migración de schema y tests.

## 7. Plan de actuación

### H00 — Documento maestro de limpieza

Este documento es H00. Fija decisiones de producto, clasificación de subsistemas, límites y tickets posteriores.

Criterio de cierre:

- Documento creado en `docs/architecture/BETA1_legacy_cleanup_audit.md`.
- Incluye decisiones de producto y tabla por subsistema.
- Declara explícitamente qué no se toca ahora.

### H01 — Limpieza de artefactos y huérfanos obvios

Acciones permitidas:

- Borrar artefactos/manuales temporales trackeados que no son runtime:
  - `tmp/`
  - `manual_pre_b27/`
  - `manual_test_b01_b18/`
  - contenido generado en `ai_outputs/`, conservando `.gitkeep` si se desea mantener el directorio.
  - `narrative_architect.egg-info/` si existe.
- Borrar widget huérfano no importado:
  - `hosts/DesktopHostPySide/widgets/relation_create_panel.py`
- Borrar directorio vacío:
  - `hosts/DesktopHostPySide/views/creation_parts/`
- Corregir documentación que mencione tooling inexistente, o documentar que el script fue retirado.

No permitido en H01:

- No borrar vistas/controladores legacy de Desktop.
- No tocar dominio.
- No tocar schema.
- No tocar IA.
- No tocar `graph_canvas.py`.
- No refactorizar `workspaces.py`.

### H02 — Retirar UI Desktop desconectada

Estado: ejecutado en 2026-06-15.

Borra físicamente vistas/controladores desconectados por A03:

- `campaign_view.py`
- `session_view.py`
- `live_post_view.py`
- `issues_history_view.py`
- controladores desconectados asociados
- clases `GalleryWorkspace`, `SessionWorkspace`, `SessionPreparationWorkspace`, `SessionOverview` dentro de `workspaces.py`

Mantener `SessionController` si sigue siendo dependencia transitoria de `ExportService`.

### H03 — Controles ocultos no funcionales

Estado: ejecutado en 2026-06-15.

Eliminar controles ocultos o no funcionales:

- dark mode oculto
- fullscreen oculto
- diagnostic toggle oculto

Si se quiere recuperar alguno, crear ticket futuro; no dejarlo escondido indefinidamente.

### H04 — Simplificar Hoja/Rama/Anillo visible

Estado: ejecutado en 2026-06-15.

- Hoja: solo persona/personaje, objeto, nota en UI normal.
- Rama: elemento contenedor/nestable con descripción.
- Anillo: siempre visible; no `layer/capa` visible.
- Localización/lugar pasa a Rama por defecto.

### H05 — Relación custom visible

Estado: ejecutado en 2026-06-15.

- Permitir tipo de relación personalizado.
- No obligar a elegir catálogo legacy de `RelationType`.
- Mantener enums internos para compatibilidad hasta migración: las etiquetas libres
  se preservan en `custom_metadata["custom_relation_label"]` usando
  `relation_type=esta_relacionado_con` como valor interno compatible.

### H06 — Candidato -> Semilla

Estado: ejecutado en 2026-06-15.

- Cambiar copy visible a Semilla.
- Mantener `Candidate` interno temporalmente.
- No tocar pipeline IA.

### H07 — Quitar visibilidad de UI

Estado: ejecutado en 2026-06-15.

- Retirar visibilidad de paneles, filtros y copy normal.
- Mantener campos internos hasta migración posterior.

### H08 — Preparar migraciones legacy

Estado: ejecutado en 2026-06-15.

Documento: `docs/architecture/BETA1_legacy_migration_plan.md`.

Documento/tickets de migración para:

- secrets/clues
- factions/fronts
- campaign/session/live/post
- writing
- frameworks
- timeline_events
- visibility

### H09+ — Migraciones reales

Estado: parcialmente iniciado; H09/H10 retiraron la capa Desktop/runtime,
pero las migraciones persistentes siguen pendientes.

Cada subsistema se migra o elimina en ticket independiente, con schema bump, tests de carga de proyectos antiguos y `run_all_tests.py`.

Subestado:

- H09 Frameworks: UI/controlador Desktop retirados; dominio, servicio, schema y
  lectura de proyectos antiguos se conservan.
- H10 Escritura: UI/controlador Desktop retirados; dominio, servicio, schema y
  lectura de proyectos antiguos se conservan.

## 8. Validación requerida

Por defecto:

```bash
python -m compileall packages hosts tests -q
python scripts/run_all_tests.py
```

Si `run_all_tests.py` falla por cambios IA paralelos o deuda ajena al ticket, se debe reportar como bloqueo externo con output real. No se declara cierre completo sin distinguir fallos propios vs baseline.

## 9. No tocar en esta fase

Queda fuera del alcance inmediato:

- Pipeline IA.
- `graph_canvas.py` salvo bug puntual.
- Refactor complejo de `workspaces.py`.
- Persistencia profunda.
- Dominio core profundo.
- Migraciones de visibility/secrets/campaign/session/framework/writing en el mismo ticket.

## 10. Decisiones pendientes de detalle

1. Confirmar si todo Lugar/Localización se crea como Rama por defecto.
2. Definir si un evento ordinario se modela como `CausalMilestone` o como otro elemento de cronología.
3. Definir almacenamiento final de relación custom: `CustomRelationType`, texto libre en relación, o ambos.
4. Definir ubicación exacta de Importación: menú proyecto/configuración vs panel dentro de Creación.

Estas decisiones no bloquean H01/H02, pero sí H04/H05/H08.
