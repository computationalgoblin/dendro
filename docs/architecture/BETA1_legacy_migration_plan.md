# BETA1 — Plan de preparación de migraciones legacy

Fecha: 2026-06-15
Estado: H08 ejecutado como planificación; migraciones reales pendientes de tickets H09+

## 1. Propósito

Este documento prepara la retirada física de subsistemas legacy que ya no pertenecen al producto BETA1 visible.

No ejecuta migraciones. No cambia schema. No borra datos persistidos.

La regla es: cada migración real debe ser un ticket independiente con:

- schema bump explícito si cambia persistencia;
- migración de carga de proyectos antiguos;
- tests de roundtrip save/load;
- tests de compatibilidad con fixtures antiguos;
- validación completa con `python scripts/run_all_tests.py` ejecutada localmente.

## 2. Decisiones de producto que guían las migraciones

BETA1 conserva:

- Creación;
- Importación;
- Hoja;
- Rama;
- Anillo;
- Relación custom;
- Semilla como nombre visible temporal de `Candidate`;
- cronología basada en `ProjectChronology` y `CausalMilestone`.

BETA1 retira conceptualmente:

- visibilidad;
- secretos/pistas;
- campañas;
- sesiones;
- live mode;
- post-session;
- facciones/frentes como subsistema propio;
- escritura;
- frameworks;
- galería;
- CLI como producto visible.

## 3. Reglas de seguridad

1. No borrar campos persistidos sin migración.
2. No confundir UI oculta con dominio eliminado.
3. No usar CLI como criterio para mantener un subsistema vivo.
4. No tocar IA en estas migraciones mientras la pipeline esté siendo corregida por otro modelo.
5. No tocar `graph_canvas.py` salvo bugs puntuales.
6. No mezclar varias migraciones en el mismo ticket.
7. No declarar completado sin tests de carga de proyectos antiguos.

## 4. Orden recomendado de migración

### H09 — Frameworks

Estado: capa Desktop/runtime retirada en 2026-06-15. Migración profunda pendiente.

Riesgo: medio.

Motivo para migrar primero:

- no forma parte de BETA1 visible;
- conceptualmente más aislado que visibilidad/sesiones;
- permite reducir ruido de UI/servicios sin tocar el core de creación.

Auditar:

- `Project.framework_templates`;
- `Project.narrative_frameworks`;
- `FrameworkService`;
- `FrameworkView`;
- `FrameworkController`;
- referencias IA a frameworks;
- tests `framework`.

Estrategia restante:

1. marcar campos como legacy en schema;
2. mantener lectura tolerante de proyectos antiguos;
3. eliminar escritura nueva desde servicios/CLI si procede;
4. borrar dominio/servicio solo en ticket posterior si ya no hay consumidores.

Hecho en H09 seguro:

- retirado `FrameworkView`;
- retirado `FrameworkController`;
- retiradas instanciaciones Desktop desde `MainWindow`;
- retirado `framework_view` de `CreationWorkspace`.

### H10 — Escritura

Estado: capa Desktop/runtime retirada en 2026-06-15. Migración profunda pendiente.

Riesgo: medio.

Auditar:

- `WritingUnit`;
- `WritingService`;
- `WritingView`;
- `WritingController`;
- exportaciones que dependan de unidades de escritura;
- tests de writing.

Estrategia restante:

1. mantener lectura de `writing_units` legacy;
2. no crear nuevas unidades desde servicios/CLI si procede;
3. migrar o ignorar datos antiguos de forma explícita;
4. retirar schema/validadores solo con bump y fixtures antiguos.

Hecho en H10 seguro:

- retirado `WritingView`;
- retirado `WritingController`;
- retiradas instanciaciones Desktop desde `MainWindow`;
- retirado `writing_view` de `CreationWorkspace`.

### H11 — Secretos/Pistas

Estado: UI Desktop especializada ya desconectada en H02/A03; exposición normal
restante retirada en 2026-06-15. Migración profunda pendiente.

Riesgo: medio-alto.

Decisión de producto:

- no hay secretos;
- no hay pistas.

Auditar:

- `Secret` / `Clue` / modelos equivalentes;
- `secrets_service.py`;
- `Project.secrets`;
- `Project.clues`;
- `EntityType.SECRETO`;
- `EntityType.PISTA`;
- importación que pueda generar secretos/pistas;
- exportación/RAG que filtre secretos.

Estrategia restante:

1. mapear datos antiguos a Hoja/Nota o descartarlos como legacy preservado;
2. retirar servicios especializados solo cuando H13 rompa dependencias de sesión/live;
3. borrar enum values solo con migración y tests.

Hecho en H11 seguro:

- `SecretsCluesView` ya estaba desconectada/retirada con `CampaignView`;
- `secrets_controller` ya estaba desconectado del runtime Desktop;
- retirados `secreto` y `pista` del filtro y creación técnica de `CorpusView`;
- retirados tonos/colores específicos `secreto`/`pista` de tarjetas genéricas;
- retirados contadores normales `secrets`/`clues` del resumen de proyecto.

### H12 — Facciones/Frentes

Estado: UI Desktop especializada ya desconectada en H02/A03; exposición normal
restante retirada en 2026-06-15. Migración profunda pendiente.

Riesgo: alto.

Decisión de producto:

- una facción es Rama;
- frentes/relojes no forman parte de BETA1.

Auditar:

- `Faction`;
- `Front`;
- `CampaignClock` si se usa para frentes;
- `EntityType.FACCION`;
- servicios/controladores CLI/UI;
- relaciones ally/enemy específicas;
- schema de `Project.factions` / `Project.fronts`.

Estrategia restante:

1. convertir facciones antiguas a `NarrativeEntity(entity_type=contenedor)` con metadata de origen;
2. archivar/ignorar frentes en colección legacy;
3. no borrar `CampaignClock` si aún lo usan campañas/sesiones hasta H13;
4. limpiar CLI después de la migración de datos.

Hecho en H12 seguro:

- `FactionFrontView` ya estaba desconectada/retirada con `CampaignView`;
- `faction_controller` ya estaba desconectado del runtime Desktop;
- retirado `faccion` del filtro y creación técnica de `CorpusView`;
- retirados tonos/colores específicos `faccion` de tarjetas genéricas;
- retirados contadores normales `factions`/`fronts` del resumen de proyecto.

### H13 — Campaña/Sesión/Live/Post

Estado: capa Desktop/runtime retirada en 2026-06-15. Migración profunda pendiente.

Riesgo: alto.

Decisión de producto:

- no campañas;
- no sesiones;
- no live mode;
- no post-session.

Auditar:

- `Campaign`;
- `Session`;
- `LiveMode`;
- `PostSession`;
- `SessionController`;
- `ExportService`;
- `Project.campaigns`;
- `Project.sessions`;
- historial asociado;
- CLI `campaign`, `session`, `live`, `post`.

Estrategia restante:

1. mantener lectura tolerante de proyectos antiguos;
2. eliminar comandos CLI legacy solo con ticket/migración;
3. migrar datos antiguos a notas/fuentes solo si hay decisión explícita;
4. borrar dominio/schema solo con fixtures antiguos y `run_all_tests.py`.

Hecho en H13 seguro:

- exportación Desktop avanzada ya solo exporta entidades;
- `ExportService` se instancia sin `SessionService` en `MainWindow`;
- retirado `SessionController` del runtime Desktop y del árbol físico `hosts/`;
- retirados `session/campaign` del selector de exportación de elemento;
- `export_all()` ya no añade totales legacy de secretos/pistas/sesiones al payload BETA1.

### H14 — TimelineEvent

Estado: capa Desktop/runtime retirada en 2026-06-15. Migración profunda pendiente.

Riesgo: medio-alto.

Decisión pendiente:

- mantener `CausalMilestone` y `ProjectChronology`;
- probablemente retirar `TimelineEvent`.

Auditar:

- `TimelineEvent`;
- `TimelineService`;
- `TimelineView`;
- `CausalMilestoneService`;
- `Project.project_chronology`;
- `Project.causal_milestones`;
- tests de chronology/timeline.

Estrategia restante:

1. mapear eventos antiguos a hitos si tienen entidad/causalidad clara;
2. preservar eventos ambiguos como notas/import legacy;
3. retirar `TimelineService`/schema solo con migración y tests;
4. no tocar `CausalMilestone` ni `ProjectChronology`, porque cronología causal es núcleo vivo.

Hecho en H14 seguro:

- retirado `TimelineView` del runtime Desktop y del árbol físico `hosts/`;
- retirado `TimelineController` del runtime Desktop y del árbol físico `hosts/`;
- `CreationWorkspace` ya no recibe ni refresca `timeline_view` legacy;
- se mantiene la UI viva de hitos causales (`CausalMilestonePanel`) y controladores de cronología causal.

### H15 — Visibilidad

Riesgo: muy alto.

Decisión de producto:

- no hay visibilidad.

Motivo para dejarlo al final:

`visibility_state` está cruzado con entidades, relaciones, exportación, RAG/contexto, graph filters, tests y schema.

Auditar:

- `VisibilityState`;
- `visibility_state` en `NarrativeEntity`;
- `visibility_state` en `NarrativeRelation`;
- `VisibilityConfig`;
- `GraphService`;
- `CorpusIndexer`;
- `NarrativeContextBuilder`;
- `ExportService`;
- filtros visuales;
- tests de privacidad/export/RAG.

Estrategia:

1. H07 ya retiró controles visibles normales;
2. dejar creación nueva con default único;
3. eliminar comportamiento que filtre por visibilidad solo cuando IA/export/RAG estén coordinados;
4. migrar campos a ausentes o ignorados;
5. borrar enum/campos solo con schema bump final.

## 5. Checklist por ticket de migración real

Cada H09+ debe incluir:

- lista de campos y colecciones persistidas afectadas;
- consumidores vivos actuales;
- decisión de mapeo de datos antiguos;
- migración `from_dict`/schema si aplica;
- tests con proyecto antiguo;
- tests con proyecto nuevo;
- test de save/open sin pérdida no prevista;
- documentación actualizada;
- búsqueda estática de referencias legacy;
- salida clara: KEEP LEGACY / MIGRATE / DELETE.

## 6. Qué queda hecho antes de migrar

- H00: contrato maestro de limpieza.
- H01: huérfanos/artefactos obvios retirados.
- H02: UI Desktop legacy desconectada retirada.
- H03: controles ocultos no funcionales retirados.
- H04: Hoja/Rama/Anillo visible simplificado.
- H05: relación custom visible integrada de forma compatible.
- H06: `Candidate` renombrado visible a Semilla.
- H07: visibilidad retirada de la UI normal.
- H08: este plan de migraciones.

## 7. Cierre

La limpieza segura de producto termina en H08.

H09+ son migraciones reales. Deben ejecutarse con tickets atómicos, modelo más potente o revisión manual estricta, y validación completa.
