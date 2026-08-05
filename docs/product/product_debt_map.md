# Product Debt Map — Dendro / Narrative Architect (BETA baseline)

Última actualización: 2026-07-21 (cierre de beta) — **una sola deuda abierta (DC-CLI-DRIFT, baja, post-beta)**. Resto saldado/cerrado: DC-AUDIT-03 (puertos), DC-AUDIT-02 (validación efectiva por flujo), DC-040 (sharding del runner), DC-001..024 (prescripción).

## Deuda activa

| ID | Descripción | Prioridad | Estado | Origen |
|----|-------------|-----------|--------|--------|
| DC-001..DC-024 | Sin evidencia documental individual | baja | descartadas por prescripción (2026-07-21, cierre de beta): heredadas de B01-B16 sin evidencia reproducible ni síntoma vigente; reabrir solo con evidencia concreta | B01-B16 |
| DC-026 | import review edit no implementado | baja | obsoleta — subsistema de importación retirado (BETA1-CLEANUP-IMPORT) | B17 |
| DC-027 | import review merge no implementado | baja | obsoleta — subsistema de importación retirado (BETA1-CLEANUP-IMPORT) | B17 |
| DC-033 | get_ordered_events sin partial_order real | baja | descartada — decisión de producto 2026-07-03 (Timeline/Redacción sin superficie GUI; solo CLI) | B27 |
| DC-034 | TimelineEvent sync con NarrativeEntity(EVENTO) | baja | descartada — decisión de producto 2026-07-03 (Timeline/Redacción sin superficie GUI; solo CLI) | B27 |
| DC-035 | IA writing provider simulado | baja | descartada — decisión de producto 2026-07-03 (fallback de test legítimo; Redacción sin GUI) | B27 |
| DC-036 | get_tree no escala >1000 entidades | baja | descartada — decisión de producto 2026-07-03 (Timeline/Redacción sin superficie GUI; solo CLI) | B27 |
| DC-040 | CLI flakes secrets/clues | baja | mitigada (2026-07-21): los flakes solo aparecían bajo ordenación de suite completa (estado global de sesión compartido); el runner (`scripts/run_all_tests.py`) ejecuta las suites en subprocesos separados y los tests pasan aislados. Aceptada como cerrada para beta; reabrir si reaparece bajo el runner | — |
| DC-044 | improvise fallback determinista | baja | obsoleta — su único consumidor (LiveModeService) está fuera del runtime desktop desde BETA1-H13 | B27 |
| DC-B28-UI-WIN | B28 sin validación Desktop Windows | media | descartada — decisión de producto 2026-07-03 (no se hará pasada formal; la validación queda en el uso real en Windows) | B28 |
| DC-034-01 | Layout contenedores no persiste posiciones | baja | descartada — decisión de producto 2026-07-03 | B34 |
| DC-034-02 | _tree_context sin cache | baja | descartada — decisión de producto 2026-07-03 (interno; reabrir solo si hay lentitud medible) | B34 |
| DC-034-03 | Collapse/expand se pierde al refrescar | baja | descartada — decisión de producto 2026-07-03 | B34 |
| DC-034-04 | Layout jerárquico Windows imperfecto | media | descartada — decisión de producto 2026-07-03 (sin bugs reproducibles; reabrir con evidencia) | B34 |
| DC-UX4-HITO | editar:hito no aplica | media | cerrada (causa real: el hito seleccionado no llegaba al contexto; se inyecta `selected_milestones` + `_apply_edit` edita `year`; verificado en real 1200→1300) | UX4 |
| DC-AUDIT-01 | La GUI no tiene punto de exportación (al retirar la vista de import/export desapareció su único consumidor) | media | **SALDADA (2026-08-01, BETA-AUDIT-04)**. Se cerró como «descartada» el 2026-07-03 apuntando a la CLI `narrative-architect export`, y tres semanas después WS-G eliminó el host CLI entero **sin reabrir esta deuda**: el producto quedó sin ninguna vía de exportación. Ahora `ExportService.export_markdown_bundle` escribe una carpeta de Markdown (un fichero por entidad con front-matter + índice, orden estable) y el panel de Proyecto la expone en «Exportar a Markdown…». LECCIÓN: cerrar una deuda delegándola en otro subsistema exige una dependencia explícita, o el subsistema se retira y la deuda revive en silencio | AUDIT-01 → BETA-AUDIT-04 |
| DC-AUDIT-02 | output_schema_validator no cubre los AIJobType nuevos y la ruta principal de jobs llama al gateway con validate=False (la validación efectiva la hace _extract_json/stage_results) | baja | cerrada (2026-07-21): tras el recorte post-WIKI la validación efectiva es POR FLUJO y dedicada — `watering_payload` (riego), `memory_payload` (memoria), `stage_results`/`_extract_json` (semillas), parseo acotado del navegador wiki — y ningún caller vivo usa `validate=True`; el validador genérico queda como opción del gateway. No se ampliará su cobertura | AUDIT-03 |
| DC-CLI-DRIFT | El host CLI no siguió la evolución del producto desktop: ~23 tests de `tests/ui/test_*_cli.py` (layer/config/gallery/entity) esperan el modelo VIEJO — capas por defecto persistidas (hoy son virtuales: se mergean en vista, `foco_rings.effective_rank_map`/`_effective_world_layers`), secciones de config pre-PA04 (`general.*`), filtros de galería (superficie desconectada en BETA1-A). Fallan aislados (no es el flake de ordenación DC-040). Cerrar post-beta: decidir si el CLI se actualiza al modelo efectivo o se recorta formalmente a project/export | baja | abierta (registrada 2026-07-21, no bloquea beta: el producto es el host desktop) | cierre-beta |
| DC-AUDIT-04 | 28 de los 82 módulos de `packages/application` son inalcanzables desde la interfaz (imports directos desde `hosts/` + cierre transitivo). No es deuda de cableado: la decisión de producto es NO exponerlos en bloque. Es deuda de **gobernanza** — el conjunto vivía sin veredicto escrito y cambiaba sin que nadie se enterara, que es exactamente cómo DC-AUDIT-01 revivió en silencio | media | **clasificada (2026-08-02, BETA-AUDIT-14)**: tabla con veredicto y razón por módulo en la sección «Módulos de `packages/application` sin superficie» de este mismo documento, atada al cálculo real por `tests/test_beta_audit_unreachable_inventory.py`. 1 `borrar` (`timeline_service`, cero importadores y cero tests), 27 `cuarentena`, 0 `cablear` | BETA-AUDIT-14 |
| DC-M2-HILO-CRONO | El hilo causal setup→payoff no se DIBUJA en el lienzo de la cronología. BETA-MULTIAGENT2-FIX-09 reparó el modelo (los hijos se derivan de los padres), la cadena, la consulta de «plantado sin recoger» y su superficie (panel de detalle con padres/hijos clicables + panel de hilos sueltos), pero el tester pedía además «dibujar el hilo»: hoy `ChronoLayout` (`chrono_canvas.py`) no tiene ningún tipo de enlace hito→hito y las marcas de hito son FRANJAS que cruzan todo el lienzo, así que un arco causal no es un cable suelto sino diseño visual nuevo (¿arco lateral?, ¿resaltar solo la cadena del hito seleccionado?, ¿solo al pasar el ratón?) | media | abierta (registrada 2026-08-04, fuera de alcance a propósito de FIX-09; decidir el diseño antes de implementarla) | G2-15 → BETA-MULTIAGENT2-FIX-09 |
| DC-AUDIT-03 | Violaciones de capas congeladas en DOCUMENTED_LAYER_DEBT (tests/architecture): application importaba infrastructure.ai_provider y persistence.store/schema | media | SALDADA (2026-07-21) — puertos en application: `ai_provider_port.py` (contrato AIProvider + provider_chat + `resolve_provider` por import dinámico; infrastructure re-exporta por compatibilidad) y `repository_port.py` (Protocol `ProjectRepository` + `default_repository` + `current_schema_version` por import dinámico). `DOCUMENTED_LAYER_DEBT` queda vacío y el guard corre sin allowlist | AUDIT-03 |

## Deuda cerrada

| ID | Descripción | Cerrada en |
|----|-------------|------------|
| DC-008 | Sin detalle | B05 |
| DC-009 | Persistencia v5 tests history | B06 |
| DC-016 | Absorbida | B12 |
| DC-022 | CandidateService sin tests | B15.8 |
| DC-024 | OrchestratorService sin tests | B15.8 |
| DC-028 | PDFExtractor requiere pymupdf (dependencia retirada de pyproject en BETA1-AUDIT-01 al eliminarse PDFExtractor) | BETA1-I08 |
| DC-045 | AnalysisService sin tests unitarios | BETA1-H01 |

## Reglas

- No renumerar IDs.
- "Mitigado" != "resuelto".
- Toda deuda nueva: DC-{bloque}-{secuencial}.

## BETA-AUDIT-14 · Módulos de `packages/application` sin superficie

Inventario verificado el 2026-08-02 por análisis de alcanzabilidad (imports directos
desde `hosts/**/*.py`, incluidos los perezosos dentro de funciones, más el cierre
transitivo dentro de la propia capa): **27 de 82 módulos son inalcanzables
desde la interfaz**.

**La decisión de fondo es NO cablearlos en bloque.** Más superficie no es más
coherencia: la app mejoró cuando la IA se recortó de 23 tipos de trabajo a 9, y volver a
exponer lint, incidencias, diagnósticos y análisis reconstruiría exactamente la
confusión que se acababa de quitar. `cuarentena` significa: se conserva, no se promete,
no se documenta como capacidad, y se reevalúa cuando exista un caso de uso concreto.

**Reevaluación 2026-08-04 (BETA-MULTIAGENT2-FIX-11).** La ronda 2 del beta multi-agente
aportó el caso de uso concreto que esta tabla pedía para el lint: medido sobre los mundos
entregados, `castilla-s-xiv.json` tenía **17 enlaces rotos** y `marjal-rojo.json` **27** —
la wiki nacía rota sin que nadie se enterara porque el detector no tenía pantalla. Se
levanta la cuarentena de los tres módulos de «qué va mal» (`wiki_lint_service`,
`issue_service`, `diagnostic_service`) y se resuelve la objeción de «dónde vive» con un
**panel único «Salud del proyecto» con pestañas** (Continuidad · Wiki · Estructura), bajo
demanda y sin contador permanente en la esquina (G2-07). De los tres:
`wiki_lint_service` **se cabla aquí** (pestaña Wiki) y sale de la tabla; los otros dos
siguen en ella porque su superficie está decidida pero no construida — ver sus filas.

Eran 29 en la auditoría original; `export_service` salió de la lista al cablearlo en
**BETA-AUDIT-04** y `wiki_lint_service` al cablearlo en **BETA-MULTIAGENT2-FIX-11**. La
guarda `tests/test_beta_audit_unreachable_inventory.py` mantiene esta tabla atada al
cálculo real: si alguien añade un módulo huérfano o cablea uno sin tocar este documento,
falla y dice cuál.

| Módulo | Líneas | Tests | Veredicto | Razón |
|--------|--------|-------|-----------|-------|
| `analysis_service` | 144 | 5 | cuarentena | Análisis de coherencia; su job type está en `_DEPRECATED_JOB_TYPES` desde el recorte de IA de BETA2-WIKI. Volver a exponerlo recrearía la superficie que se quitó. |
| `bootstrap` | 119 | 2 | cuarentena | Arranque de la app para un host que ya no existe: el escritorio construye su propio `AppContext`. Se conserva por si vuelve un host sin GUI. |
| `campaign_service` | 544 | 4 | cuarentena | Vertical de rol, fuera de la beta por decisión de producto (BETA-CIERRE WS-A). No se promete ni se borra. |
| `candidate_dedup` | 129 | 2 | cuarentena | Deduplicación de candidatos; hoy `stage_results` estadía sin deduplicar. Útil si las Semillas llegan a producir duplicados de verdad. |
| `causal_milestone_reviewer` | 142 | 1 | cuarentena | Revisión asistida de hitos; pertenece a la superficie de IA recortada. |
| `creative_context` | 64 | 2 | cuarentena | Ensamblado de contexto creativo previo a PA04; lo sustituyó `prompt_assembler` con presupuestos por tramo. |
| `custom_type_service` | 350 | 1 | cuarentena | Tipos personalizados. **La razón anterior era falsa** (verificado en BETA-MULTIAGENT2-FIX-11): el combo editable de la Ficha NO crea ningún `CustomRelationType` — `relation_detail_panel` escribe una etiqueta cosmética en `custom_metadata["custom_relation_label"]` y degrada el tipo real a `esta_relacionado_con`. Es decir, la UI se fabricó un modelo paralelo porque el de verdad no tiene puerta. Sigue en cuarentena, pero por falta de superficie decidida, no porque esté cubierto. Lo destapa G2-16 / BETA-MULTIAGENT2-FIX-12. |
| `diagnostic_service` | 287 | 2 | cuarentena | Diagnósticos de proyecto (integridad referencial y recuentos de limpieza). Cuarentena levantada en BETA-MULTIAGENT2-FIX-11 y **medido antes de cablear**: 0 items, 0 errores y 0 avisos sobre `castilla-s-xiv` (24 entidades) y `marjal-rojo` (800). Cablearlo hoy sería añadir una pantalla vacía; se reevalúa si algún mundo real le saca contenido. |
| `faction_service` | 389 | 3 | cuarentena | Vertical de rol, fuera de la beta por decisión de producto (BETA-CIERRE WS-A). |
| `framework_service` | 444 | 1 | cuarentena | Marcos narrativos (estructuras tipo tres actos). Idea viva, sin superficie decidida; requiere diseño de UX antes que código. |
| `graph_layout` | 174 | 1 | cuarentena | Layout de grafo del host retirado; el Mapa usa `packages/ui/graph_physics`. Se conserva como referencia del algoritmo. |
| `graph_models` | 472 | 5 | cuarentena | Modelos del grafo servidos al host CLI retirado; el escritorio tiene sus propios `_NodeView`/`_EdgeView`. |
| `graph_service` | 576 | 2 | cuarentena | Consultas de grafo para el CLI retirado. Solapa con lo que el lienzo calcula en memoria. |
| `issue_service` | 514 | 3 | cuarentena | Incidencias estructuradas (15 validadores deterministas). Cuarentena levantada en BETA-MULTIAGENT2-FIX-11 con datos a favor: medido sobre los mundos del beta da 5 / 20 / 2 / 155 incidencias, y **19 de las 20 del mundo de Aitor son `no_description`** — habría cazado el bloqueante G2-03 el día que se escribió. No se cabla todavía porque su sitio es la pestaña **Continuidad** del panel «Salud del proyecto» (BETA-MULTIAGENT2-FIX-10) y necesita dos cautelas: usar la función pura `run_validators(project)` —`run_validation` ESCRIBE en `project.issues` y eso se persiste— y filtrar las familias muertas (`secret_without_clue`, de la vertical de rol retirada: 48 de 155 en el mundo grande; y `pending_import`). **Estado tras BETA-MULTIAGENT2-FIX-10 (2026-08-04)**: la pestaña Continuidad ya existe, pero la sirve `continuity_service` (motor temporal/causal determinista de BETA1-J02) y **NO absorbe `issue_service`**, que sigue en cuarentena tal cual: FIX-10 lo dejó explícitamente fuera de alcance para no reabrir la decisión de BETA-AUDIT-14 por la puerta de atrás. Quien lo cablee tendrá sitio donde ponerlo (`ProjectHealthPanel.add_section`) y deberá retirar esta fila. |
| `live_mode_service` | 192 | 2 | cuarentena | Vertical de rol (mesa en directo), fuera de la beta por decisión de producto (BETA-CIERRE WS-A). |
| `narrative_context_builder` | 987 | 6 | cuarentena | 987 líneas de ensamblado de contexto anteriores a la wiki navegable; hoy lo hace `wiki_navigator` + `prompt_assembler`. El módulo más grande del inventario. |
| `neighborhood` | 95 | 8 | cuarentena | Vecindad de entidades; el cálculo equivalente vive en `foco_rings` y en el propio lienzo. |
| `post_session_service` | 177 | 2 | cuarentena | Vertical de rol (cierre de sesión), fuera de la beta por decisión de producto (BETA-CIERRE WS-A). |
| `query_service` | 379 | 4 | cuarentena | Consultas estructuradas del CLI retirado. Su caso de uso lo cubre hoy el buscador del Mapa (BETA-AUDIT-10). |
| `repair_plan_service` | 198 | 1 | cuarentena | Planes de reparación de canon; su cadena (`repair_coherence`) está viva pero INERTE — ver nota abajo. |
| `secrets_service` | 466 | 3 | cuarentena | Vertical de rol (secretos y pistas de mesa), fuera de la beta (BETA-CIERRE WS-A). No confundir con la visibilidad reservada de entidades, que sí es del producto y la devolvió BETA-AUDIT-02. |
| `session_service` | 230 | 5 | cuarentena | Vertical de rol, fuera de la beta por decisión de producto (BETA-CIERRE WS-A). |
| `status_quo_explainer` | 103 | 1 | cuarentena | Explicación del estado del mundo en un momento dado. Solapa con la página de wiki que ya escribe Regar. |
| `structured_coherence` | 110 | 1 | cuarentena | Coherencia estructurada; pertenece a la superficie de IA recortada en BETA2-WIKI. |
| `text_search_service` | 228 | 2 | cuarentena | Búsqueda de texto completo. BETA-AUDIT-10 resolvió la necesidad ampliando el índice local del Mapa (alias + cuerpo) sin añadir una segunda superficie de búsqueda. Reevaluar si aparece el caso de buscar por campo o en relaciones. |
| `timeline_service` | 192 | 0 | borrar | **Cero importadores y cero ficheros de test en todo el repo.** La cronología la llevan `causal_milestone_service` + `project_chronology` + el calendario de dominio. Es el único módulo del inventario sin ninguna atadura. |
| `writing_service` | 413 | 1 | cuarentena | Generación de texto en prosa; su superficie (texto inline) se retiró en BETA2-WIKI. |

**Nota sobre `coherence_repair`** (no cuenta entre los 28): sí es alcanzable
—lo importan 6 ficheros del escritorio y `views/workspaces.py` referencia
`AIJobType.REPAIR_COHERENCE`— pero la cadena está **inerte**: nada crea ese job porque su
tipo vive en `_DEPRECATED_JOB_TYPES`, así que `on_repair` no dispara nunca. Está cubierta
por dos tests, de modo que retirarla es un refactor coordinado multi-fichero con riesgo
sobre el core y sin valor visible para el usuario. WS-G ya lo evaluó y decidió dejarlo;
esta épica mantiene esa decisión.
