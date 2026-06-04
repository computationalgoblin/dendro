# B32 — Implementation inventory

Fecha: 2026-06-04
Rama auditada: `feature/B31-immersive-ux`
Alcance: lectura de `packages/application/`, `packages/domain/`, `packages/persistence/`, `hosts/DesktopHostPySide/`, `tests/`, `docs/` y `scripts/`.

Nota de integridad: el working tree ya estaba sucio al iniciar B32. Esta auditoría no modifica funcionalidad; solo documenta hallazgos.

Estados usados:
- OK: implementado y con uso/cobertura razonable.
- PARTIAL: implementado parcialmente o con gaps claros.
- RISK: implementado pero con riesgo arquitectónico/UX.
- BROKEN: fallo reproducido o contrato incumplido.
- UNKNOWN: requiere validación manual o ejecución no disponible.

| Área | Archivo/Servicio/Vista | Estado | Usado en UI | Usado en CLI | Tests | Problemas | Decisión propuesta |
|---|---|---:|---:|---:|---|---|---|
| Domain | `packages/domain/project.py` / `Project` | RISK | Sí | Sí | `test_project_service`, schema tests | Aggregate root muy cargado; aliases `issues/structured_issues`; muchas colecciones de bloques previos. | CORE. Mantener; no ampliar sin limpieza de contrato. |
| Domain | `packages/domain/entity.py` / `NarrativeEntity` | OK | Sí | Sí | domain/entity, app/entity, persistence/entity | Campos legacy `domain/layers` conviven con `domain_ids/layer_ids`; B32 añade `EntityType.CONTENEDOR`. | CORE. Mantener; definir canon de campos legacy. |
| Domain | `packages/domain/relation.py` / `NarrativeRelation` | RISK | Sí | Sí | domain/relation, app/relation | API canónica `source_id/target_id`; algunas vistas B32 parecen usar `source_entity_id/target_entity_id`. | CORE. Normalizar consumidores a `source_id/target_id`. |
| Domain | `packages/domain/candidate_issue.py` | RISK | Sí | Sí | candidate/issue tests | Conviven `Issue` legacy y `StructuredIssue`; candidatos de IA/importación pueden confundirse en UX. | CORE para revisión; ocultar legacy en UI normal. |
| Domain | `packages/domain/import_models.py` | PARTIAL | Sí | Sí | import models/service | `ImportCandidate` es staging y duplica concepto de `Candidate`; debe comunicarse como bandeja de importación. | SUPPORT. Mantener pero unificar lenguaje con candidatos globales. |
| Domain | `packages/domain/ai_models.py` | OK | Sí | Sí | ai/context tests | Modos IA crecen; necesita separar texto inline vs candidate graph actions. | SUPPORT. Mantener. |
| Domain | `packages/domain/world_layer.py` | PARTIAL | Sí | Sí | world layer tests | Worldbuilding repartido entre capas, dominios, `worldbuilding_active`, árboles y metadata. | CORE para worldbuilding; no exponer crudo en UI normal. |
| Domain | `packages/domain/narrative_domain.py` | OK | Indirecto | Sí | domain/layer tests | Convive con campos legacy. | SUPPORT/CORE worldbuilding. |
| Domain | `packages/domain/custom_types.py` | OK | Sí | Sí | custom type tests | Complejo para usuario normal. | SUPPORT; mover a avanzado. |
| Domain | `packages/domain/session_models.py` | OK | Sí | Sí | session tests | Módulo potente pero fuera del foco Creación actual. | LATER para B38. |
| Domain | `packages/domain/campaign_models.py` | OK | Sí | Sí | campaign tests | Visible puede saturar si proyecto no es campaña. | LATER; visible solo si tipo campaña. |
| Domain | `packages/domain/secrets_models.py` | OK | Sí | Sí | secrets tests | Superficie especializada. | LATER; ocultar en modo normal fuera de sesión/campaña. |
| Domain | `packages/domain/faction_models.py` | OK | Sí | Sí | faction tests | Superficie especializada. | LATER. |
| Domain | `packages/domain/writing_models.py` | OK | Sí | Sí | writing QA | Puede solaparse con Galería/Creación. | SUPPORT/LATER. |
| Application | `project_service.py` | OK | Sí | Sí | `test_project_service` | Mutación en memoria + save explícito debe seguir claro. | CORE. |
| Application | `entity_service.py` | RISK | Sí | Sí | entity service tests | Docstring sugiere persistencia inmediata, implementación depende de `ProjectService.save`. | CORE; actualizar contrato/doc si procede. |
| Application | `relation_service.py` | RISK | Sí | Sí | relation service tests | Usa/acepta `conditions`, pero modelo tiene `validity_conditions`; posible atributo dinámico no serializado. | CORE; P1 de limpieza técnica. |
| Application | `graph_service.py` / `graph_models.py` | OK | Sí | Sí | graph tests | Debe seguir siendo vista derivada, no base de datos. | CORE para Creación. |
| Application | `graph_layout.py` | OK | Sí | No directo | layout tests | Posiciones layout no persisten como deuda conocida. | SUPPORT. |
| Application | `narrative_context_builder.py` | OK | Sí | Sí | context tests | Muy cargado; B32 añade `tree_membership`. | CORE para IA contextual. |
| Application | `ai_context_actions.py` | RISK | Sí | Sí | ai context tests | Archivo grande; riesgo de mezclar inline text con candidates; B31 fix separa `node_text_suggestion`. | CORE; separar routing por tipo de acción. |
| Application | `tree_meta.py` | PARTIAL | Sí | No claro | `test_tree_meta` | Helper en application con metadata libre; si árbol es core debería tener contrato más fuerte. | SUPPORT ahora; CORE si B34 formaliza árboles. |
| Application | `candidate_service.py` | RISK | Sí | Sí | candidate service tests | Integración con HistoryService parece llamar `add_entry` inexistente y se silencia. | CORE para revisión; auditar en B33/B35. |
| Application | `import_service.py` | PARTIAL | Sí | Sí | import service tests | Heurísticas básicas; posible duplicado con CandidateView. | SUPPORT; visible como “Importar material”, no feature central. |
| Application | `query_service.py` / `text_search_service.py` | OK | Sí | Sí | query/search tests | Base para Galería, pero Galería no es prioridad. | SUPPORT. |
| Application | `world_layer_service.py` | OK | Sí | Sí | world layer tests | UI de capas debe ocultarse si worldbuilding off. | CORE para worldbuilding. |
| Application | `custom_type_service.py` | OK | Sí | Sí | custom type tests | Técnico para usuario normal. | SUPPORT; avanzado. |
| Application | `history_service.py` / `source_service.py` | OK | Sí | Sí | history/source tests | Trazabilidad necesaria, UI cruda debe estar oculta. | SUPPORT/CORE trazabilidad. |
| Application | `diagnostic_service.py` / `repair_plan_service.py` | OK | Sí | Sí | maintenance tests | Diagnóstico no debe aparecer como superficie normal hasta funcionar visualmente. | SUPPORT; configuración/avanzado. |
| Application | `session_service.py`, `live_mode_service.py`, `post_session_service.py` | OK | Sí | Sí | session/live/post tests | Demasiada superficie para Home si no es campaña. | LATER; B38. |
| Application | `writing_service.py`, `timeline_service.py`, `framework_service.py` | OK | Sí | Sí | writing/timeline/framework tests | Vistas tipo admin/tablas. | LATER/SUPPORT; ocultar avanzado si distrae. |
| Persistence | `schema.py` | OK | Indirecto | Indirecto | schema tests | v21 enum-only para contenedor; no valida metadata B32. | CORE; añadir validaciones solo cuando B32 contrato se cierre. |
| Persistence | `store.py` | RISK | Sí | Sí | store/backup tests | Mezcla I/O con CRUD Entity/Relation legacy; imports privados de schema. | CORE; no usar CRUD legacy en rutas nuevas. |
| Desktop | `main_window.py` | RISK | Sí | No | UI static/offscreen | Orquesta muchas vistas; provider IA contextual necesita refresco al cambiar settings. | CORE UI; reducir superficie visible. |
| Desktop | `views/home_view.py` | PARTIAL | Sí | No | UI static | Home debe gobernarse por tipo de proyecto; evitar schema/provider visibles. | CORE UX. |
| Desktop | `views/workspaces.py` / `CreationWorkspace` | RISK | Sí | No | UI static | Mezcla grafo, utilidades, top toolbar, candidatos, imports, layers; requiere MVP estable. | CORE para B33. |
| Desktop | `widgets/graph_canvas.py` | RISK | Sí | No | UI static | Grafo central; evitar botones muertos y nodos IA fantasma. | CORE. |
| Desktop | `widgets/node_detail_panel.py` | PARTIAL | Sí | No | regression static/direct | IA inline corregida pero requiere validación Windows; no debe crear candidates. | CORE. |
| Desktop | `widgets/relation_detail_panel.py` | PARTIAL | Sí | No | UI static | Debe seguir patrón IA inline de nodo. | CORE para B33. |
| Desktop | `widgets/tree_detail_panel.py` | BROKEN | Sí | No | B32 static 26/28 | No cumple contrato estático: falta `membershipChanged` y métodos esperados; posibles campos `source_entity_id`. | P0/P1 antes de B34. |
| Desktop | `widgets/settings_panels.py` | PARTIAL | Sí | No | UI static | Preferencias IA/app persisten; probar Windows. | SUPPORT. |
| Desktop | `widgets/right_drawer.py` / `left_drawer.py` | OK | Sí | No | UI static | Drawers son patrón correcto; no abrir ventanas externas salvo file/color dialogs. | CORE UI shell. |
| Desktop | `views/import_export_view.py` | PARTIAL | Sí | No | import tests indirectos | Copy “Importar TXT” aunque acepta TXT/PDF; duplica CandidateView. | SUPPORT; renombrar y ocultar detalles. |
| Desktop | `views/candidate_view.py` | RISK | Sí | No | candidate tests indirectos | Tabla técnica y duplicidad con import/candidatos IA. | SUPPORT; modo avanzado o tarjetas. |
| Desktop | `views/corpus_view.py` | RISK | Sí | No | UI static | Corpus técnico duplica grafo como lista de entidades. | HIDE en normal hasta rediseñar como biblioteca. |
| Desktop | `views/relation_view.py` | RISK | Sí | No | relation tests indirectos | Tabla administrativa duplica grafo/detalle. | HIDE en normal; usar como avanzado. |
| Desktop | `views/session_view.py`, `live_post_view.py` | OK/RISK | Sí | No | session tests indirectos | Muchos controles; visible solo si campaña. | LATER/B38. |
| Desktop | `views/timeline_view.py`, `writing_view.py`, `framework_view.py` | PARTIAL | Sí | No | mixed | Útiles pero fuera del MVP Creación; tablas técnicas. | LATER/SUPPORT. |
| Tests | `tests/` | RISK | No | No | 87 `test_*.py`, 1506 funcs AST | pytest no instalado en WSL; run_all_tests no incluye desktop/infrastructure. | SUPPORT; arreglar entorno antes de cierres. |
| Docs | `docs/` | RISK | No | No | n/a | B30/B31 docs parcialmente obsoletas; faltaba B32 product audit. | SUPPORT; estos entregables cubren B32. |
| Scripts | `scripts/run_all_tests.py` | PARTIAL | No | Sí | n/a | Omite suites `desktop` e `infrastructure`; pytest ausente. | SUPPORT; actualizar en bloque QA, no ahora. |
| Scripts | `smoke_b30_20_flows.py`, PS1 B27.x | OK/LATER | No | Sí | n/a | Smokes útiles pero no cubren B31/B32 UX. | SUPPORT; crear smoke B33/B34 cuando se implemente. |
