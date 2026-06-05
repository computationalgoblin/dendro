# B42 — Auditoría Técnica Completa de Rutas IA

> Fecha: 2026-06-05  
> Proyecto: narrative-architect  
> Objetivo: Mapa exacto de cada ruta IA real encontrada en el código fuente.

---

## Tabla Resumen

| # | Ruta IA | Archivo(s) | Proveedor | creative_brief | branch_creative_context | Recomendación |
|---|---------|-----------|-----------|----------------|------------------------|---------------|
| 1 | Command Bar Jobs | `ai_jobs.py` | `create_provider()` via `.chat()` | SI | SI | KEEP |
| 2 | Entity Text Suggestion (node) | `ai_context_actions.py` | `create_provider()` via `.chat()` | SI (en contexto) | indirecto | KEEP |
| 3 | Relation Text Suggestion | `ai_context_actions.py` | `create_provider()` via `.chat()` | SI (en contexto) | indirecto | KEEP |
| 4 | Selection Coherence Analysis | `ai_context_actions.py` | `create_provider()` via `.chat()` | SI (en prompt) | indirecto | KEEP |
| 5 | Selection Coherence Repair | `ai_context_actions.py` | `create_provider()` via `.chat()` | SI (en contexto) | indirecto | KEEP |
| 6 | Node Actions (invoke) | `ai_context_actions.py` | `create_provider()` via `.invoke()` | indirecto (AuthorizedContext) | no | WRAP |
| 7 | Relation Actions (invoke) | `ai_context_actions.py` | `create_provider()` via `.invoke()` | indirecto (AuthorizedContext) | no | WRAP |
| 8 | Graph Actions (invoke) | `ai_context_actions.py` | `create_provider()` via `.invoke()` | indirecto (AuthorizedContext) | no | WRAP |
| 9 | Orchestrator invoke | `orchestrator_service.py` | `create_provider()` via `.invoke()` | no | no | WRAP |
| 10 | Orchestrator generate_candidates | `orchestrator_service.py` | `create_provider()` via `.invoke()` | no | no | LEGACY |
| 11 | Orchestrator improvise | `orchestrator_service.py` | `create_provider()` via `.invoke()` | no | no | WRAP |
| 12 | Analysis Critical | `analysis_service.py` | via OrchestratorService | no | no | WRAP |
| 13 | Analysis Causal | `analysis_service.py` | via OrchestratorService | no | no | WRAP |
| 14 | Analysis Consistency | `analysis_service.py` | via OrchestratorService | no | no | WRAP |
| 15 | Writing expand/critique/rewrite | `writing_service.py` | via OrchestratorService | no | no | WRAP |
| 16 | Writing summarize | `writing_service.py` | via OrchestratorService | no | no | LEGACY |
| 17 | Session suggest_material | `session_service.py` | via OrchestratorService (pero NO llama IA real) | no | no | REMOVE_LATER |
| 18 | LiveMode improvise | `live_mode_service.py` | via OrchestratorService | no | no | WRAP |
| 19 | AIController generate_entity_candidates | `ai_controller.py` | via OrchestratorService | no | no | LEGACY |
| 20 | AIController rewrite_entity | `ai_controller.py` | via OrchestratorService | no | no | LEGACY |
| 21 | AIController test_provider | `ai_controller.py` | via OrchestratorService | no | no | KEEP |
| 22 | AIController chat | `ai_controller.py` | `provider.chat()` directo | no | no | KEEP |
| 23 | AIContextController chat | `ai_context_controller.py` | `provider.chat()` directo | no | no | KEEP |
| 24 | CLI ai generate-entity | `cli_ai.py` | via OrchestratorService | no | no | LEGACY |
| 25 | CLI ai generate-relation | `cli_ai.py` | via OrchestratorService | no | no | LEGACY |
| 26 | CLI ai expand | `cli_ai.py` | via OrchestratorService | no | no | LEGACY |
| 27 | CLI ai summarize | `cli_ai.py` | via OrchestratorService | no | no | LEGACY |
| 28 | CLI ai rewrite | `cli_ai.py` | via OrchestratorService | no | no | LEGACY |
| 29 | CLI ai suggest-tags | `cli_ai.py` | via OrchestratorService | no | no | LEGACY |
| 30 | CLI ai suggest-relations | `cli_ai.py` | via OrchestratorService | no | no | LEGACY |
| 31 | CLI ai continuity | `cli_ai.py` | via OrchestratorService | no | no | LEGACY |
| 32 | CLI ai analyze | `cli_ai.py` | via AnalysisService | no | no | LEGACY |
| 33 | CLI ai causal | `cli_ai.py` | via AnalysisService | no | no | LEGACY |
| 34 | CLI ai consistency | `cli_ai.py` | via AnalysisService | no | no | LEGACY |
| 35 | Node Detail Inline Edit Suggestion | `node_detail_panel.py` (UI Worker) | via `ai_controller.chat()` | no | no | KEEP |
| 36 | Tree Detail Text Suggestion | `tree_detail_panel.py` (UI Worker) | via `ai_context_controller.node_text_suggestion()` | SI (en contexto) | indirecto | KEEP |
| 37 | Coherence Panel Analyze | `coherence_panel.py` (UI Worker) | via `ai_context_controller.analyze_coherence()` | SI (en prompt) | indirecto | KEEP |
| 38 | Coherence Panel Repair | `coherence_panel.py` (UI Worker) | via `ai_context_controller.repair_coherence()` | SI (en contexto) | indirecto | KEEP |

---

## Infraestructura de Proveedores

### AIProvider (ABC)
- **Archivo**: `packages/infrastructure/ai_provider.py`
- **Métodos**: `invoke(operation: AIOperation) -> AIResponse`, `chat(system_prompt, user_message, timeout) -> (text, error)`
- **Método fábrica**: `create_provider(name, config)` → delega a `get_provider()`

### SimulatedAIProvider
- **Archivo**: `packages/infrastructure/ai_provider.py`
- **Cubre todos los AIMode**: GENERATE_ENTITY, GENERATE_RELATION, EXPAND_ENTITY, SUMMARIZE, REWRITE_DESCRIPTION, SUGGEST_TAGS, SUGGEST_RELATIONS, CRITICAL_ANALYSIS, CAUSAL_ANALYSIS, CONSISTENCY_ANALYSIS, CONTINUITY_QUESTION
- **Retorna respuestas deterministas** para tests de UI sin API key

### OpenAICompatibleProvider
- **Archivo**: `packages/infrastructure/openai_compatible_provider.py`
- **Env vars**: `NARRATIVE_AI_PROVIDER`, `NARRATIVE_AI_BASE_URL`, `NARRATIVE_AI_API_KEY`, `NARRATIVE_AI_MODEL`, `NARRATIVE_AI_TIMEOUT`
- **Fallback automático**: si falta API key o base URL, degrada a `SimulatedAIProvider` con observación de fallback
- **`invoke()`**: genera prompt con `_build_prompt()` → formato `[{mode}] instruction. Context: {context}.` (muy básico)
- **`chat()`**: usa system_prompt + user_message con max_tokens=2000

### get_provider()
- **Archivo**: `packages/infrastructure/openai_compatible_provider.py`
- Si `NARRATIVE_AI_PROVIDER == "openai_compatible"` → `OpenAICompatibleProvider()`
- Sino → `SimulatedAIProvider()`

---

## Modelos de Dominio IA

### AIMode (Enum)
`GENERATE_ENTITY | GENERATE_RELATION | EXPAND_ENTITY | SUMMARIZE | REWRITE_DESCRIPTION | SUGGEST_TAGS | SUGGEST_RELATIONS | CONTINUITY_QUESTION | CRITICAL_ANALYSIS | CAUSAL_ANALYSIS | CONSISTENCY_ANALYSIS`

### AuthorizedContext
Datos autorizados que viajan al provider: project_name, selected_entity_ids, allowed_canon_states, project_config_snapshot, context_entities, context_relations, etc.

### AIOperation
Mode + context + prompt_hint + entity_id + max_candidates.

### AIResponse
id, operation, raw_text, candidates[], observations[], error, provider, latency_ms.

---

## Detalle por Ruta

---

### Ruta 1: Command Bar Jobs

| Campo | Detalle |
|-------|---------|
| **Nombre** | Command Bar Jobs (AIJobService) |
| **Archivos** | `packages/application/ai_jobs.py`, `hosts/DesktopHostPySide/views/workspaces.py` |
| **Función de entrada** | `AIJobService.create_job()` → `execute_job()` |
| **Prompt system** | `COMMAND_BAR_SYSTEM_PROMPT_ES` — prompt masivo en español con reglas de clasificación, terminología Dendro (hoja/rama/anillo), reglas B40 creative_brief, formato de salida JSON estricto |
| **Prompt user** | `build_model_user_message(plan)` — JSON con `prompt_exacto_usuario`, `intent`, `plan`, `contexto_autorizado`, `perfil_creativo_b40`, `restricciones` |
| **Formato entrada** | `prompt: str` + `context_scope: dict` (selected_entity_ids, creative_brief, branch_creative_context, worldbuilding_active, etc.) |
| **Formato salida esperado** | JSON con: `summary`, `report`, `hojas[]`, `ramas[]`, `relations[]`, `entity_edits[]`, `issues[]`, `proposals[]`, `open_questions[]` |
| **Formato salida real** | JSON parseado por `_extract_json()` → staging por `stage_results()` → candidatos revisables |
| **Proveedor** | `create_provider()` → `.chat(system_prompt, user_message)` |
| **creative_brief** | **SI** — incluido en `_b40_prompt_profile()` → `perfil_creativo_b40` del user message. Incluye hard_rules, negative_space, taste_memory, ai_preferences |
| **branch_creative_context** | **SI** — `_b40_prompt_profile()` lee `ctx.get("branch_creative_context", [])` y lo pasa como `selected_branch_overrides` |
| **Tipos de job** | GENERATE_ENTITIES, GENERATE_TREE, SUGGEST_RELATIONS, ANALYZE_COHERENCE, EXPAND_WORLDBUILDING, EXPLAIN_FROM_CAUSES, REVIEW_GRAPH, FREEFORM_PLANNING, EDIT_ENTITIES, PROPOSE_MILESTONES |
| **Clasificador** | `classify_intent()` — heurística local por keywords (sin IA) |
| **Riesgos** | El system prompt es solo ES; no hay versión EN. `allow_simulated=False` por defecto, falla limpiamente sin provider. JSON parsing tolerante pero puede perder datos en respuestas no estructuradas. |
| **Recomendación** | **KEEP** — ruta principal de la command bar, bien estructurada, con B40 completo. |

---

### Ruta 2: Entity Text Suggestion (Inline Node)

| Campo | Detalle |
|-------|---------|
| **Nombre** | Entity Text Suggestion (node) |
| **Archivos** | `packages/application/ai_context_actions.py` → `run_node_text_suggestion()`, `hosts/DesktopHostPySide/controllers/ai_context_controller.py` → `node_text_suggestion()` |
| **Función de entrada** | `AIContextActionService.run_node_text_suggestion()` |
| **Prompt system** | `_ENTITY_TEXT_SYSTEM_PROMPT_ES` / `_ENTITY_TEXT_SYSTEM_PROMPT_EN` — asistente de escritura, retorna solo texto sugerido, sin JSON |
| **Prompt user** | `_entity_text_user_prompt()` — nombre, tipo, brief_description, body, notas, género, tono, realismo, estilo narrativo, worldbuilding activo, neighborhood, causal_context, instrucción del usuario |
| **Formato entrada** | `entity_id: str`, `prompt_hint: str`, `audience: str`, `language: str` |
| **Formato salida esperado** | Texto plano (no JSON, no candidatos) |
| **Formato salida real** | Texto plano — se devuelve como `raw_text` en `AIContextActionResult` con `candidates=[]` y un preview |
| **Proveedor** | `create_provider()` → `.chat()` |
| **creative_brief** | **SI** — incluido en el contexto del proyecto que construye `NarrativeContextBuilder` via `project_creative_brief(project)` |
| **branch_creative_context** | Indirecto — el contexto de la entidad incluye neighborhood y causal_context pero no inyecta branch overrides explícitos en el prompt |
| **Riesgos** | No genera candidatos: el texto queda solo en UI hasta que el usuario acepta. Sin validación de longitud. |
| **Recomendación** | **KEEP** — ruta inline limpia para sugerencias de texto. |

---

### Ruta 3: Relation Text Suggestion

| Campo | Detalle |
|-------|---------|
| **Nombre** | Relation Text Suggestion |
| **Archivos** | `packages/application/ai_context_actions.py` → `run_relation_text_suggestion()` |
| **Función de entrada** | `AIContextActionService.run_relation_text_suggestion()` |
| **Prompt system** | `_RELATION_TEXT_SYSTEM_PROMPT_ES` / `_RELATION_TEXT_SYSTEM_PROMPT_EN` |
| **Prompt user** | `_relation_text_user_prompt()` — source_full, target_full, relation_type, direction, description, body, temporality, causality, notes, género, tono, etc. |
| **Formato entrada** | `relation_id: str`, `prompt_hint: str`, `audience: str`, `language: str` |
| **Formato salida real** | Texto plano (no JSON) |
| **Proveedor** | `create_provider()` → `.chat()` |
| **creative_brief** | **SI** — via contexto de proyecto |
| **branch_creative_context** | Indirecto |
| **Riesgos** | Similar a Ruta 2, sin candidatos. |
| **Recomendación** | **KEEP** |

---

### Ruta 4: Selection Coherence Analysis

| Campo | Detalle |
|-------|---------|
| **Nombre** | Selection Coherence Analysis |
| **Archivos** | `packages/application/ai_context_actions.py` → `run_selection_coherence_analysis()` |
| **Función de entrada** | `AIContextActionService.run_selection_coherence_analysis()` |
| **Prompt system** | `_COHERENCE_SYSTEM_PROMPT_ES` / `_COHERENCE_SYSTEM_PROMPT_EN` — editor de coherencia narrativa, usa creative_brief explícitamente (canon.hard_rules, continuity_strictness, negative_space, taste_memory, ai_preferences). Estructura: Veredicto global, Observaciones por entidad, Contradicciones, Huecos de motivación, Continuidad, Riesgos tonales, Oportunidades dramáticas, Propuestas, Preguntas abiertas. |
| **Prompt user** | `_selection_coherence_user_prompt()` — proyecto, idioma, género, tono, realismo, selected entities/relations, nearby_context, causal_context, instrucción |
| **Formato entrada** | `entity_ids: list[str]`, `relation_ids: list[str]`, `prompt_hint`, `audience`, `language` |
| **Formato salida real** | Texto estructurado (no JSON) con secciones de informe |
| **Proveedor** | `create_provider()` → `.chat()` |
| **creative_brief** | **SI** — explícitamente referenciado en el system prompt |
| **branch_creative_context** | Indirecto (via causal_context del NarrativeContextBuilder) |
| **Riesgos** | Depende de que el modelo siga la estructura de secciones. Sin parseo estructurado del output. |
| **Recomendación** | **KEEP** — ruta central de coherencia B35. |

---

### Ruta 5: Selection Coherence Repair

| Campo | Detalle |
|-------|---------|
| **Nombre** | Selection Coherence Repair |
| **Archivos** | `packages/application/ai_context_actions.py` → `run_selection_coherence_repair()` |
| **Función de entrada** | `AIContextActionService.run_selection_coherence_repair()` |
| **Prompt system** | `_COHERENCE_REPAIR_SYSTEM_PROMPT_ES` / `_COHERENCE_REPAIR_SYSTEM_PROMPT_EN` — genera reparación + bloque JSON estricto entre `<PATCH_JSON>` y `</PATCH_JSON>` con formato `{entities: [{id, brief_description, extended_description}], relations: [{id, description, body}]}` |
| **Prompt user** | `_selection_repair_user_prompt()` — contexto de coherencia + propuesta de reparación elegida |
| **Formato entrada** | `entity_ids`, `relation_ids`, `proposal: str`, `prompt_hint`, `audience`, `language` |
| **Formato salida real** | Texto narrativo + bloque PATCH_JSON |
| **Proveedor** | `create_provider()` → `.chat()` |
| **creative_brief** | **SI** — via contexto |
| **branch_creative_context** | Indirecto |
| **Riesgos** | El parseo de `<PATCH_JSON>` no está implementado en esta ruta — el resultado se devuelve como raw_text. Falta extractor de PATCH_JSON. |
| **Recomendación** | **KEEP** pero necesita implementar extractor de `<PATCH_JSON>` para aplicar reparaciones. |

---

### Ruta 6-8: Node/Relation/Graph Actions (invoke)

| Campo | Detalle |
|-------|---------|
| **Nombre** | Node Actions / Relation Actions / Graph Actions |
| **Archivos** | `packages/application/ai_context_actions.py` → `run_node_action()`, `run_relation_action()`, `run_graph_action()` → delegan a `_run()` |
| **Función de entrada** | `AIContextActionService._run()` |
| **Prompt** | `self._prompt(action_type, prompt_hint, context)` — texto corto: `"Acción IA contextual: {action_type}\nRestricciones: ...\nResumen: {JSON compacto}\nInstrucción adicional: {prompt_hint}"` |
| **Mecanismo** | Construye `AIOperation` con `AIMode` mapeado desde action_type → llama `provider.invoke(operation)` |
| **Mapeo node actions** | generate_text→EXPAND_ENTITY, improve_text→REWRITE_DESCRIPTION, suggest_relations→SUGGEST_RELATIONS, suggest_conflict→CRITICAL_ANALYSIS, suggest_secrets→CONTINUITY_QUESTION, suggest_clues→CONTINUITY_QUESTION, detect_contradictions→CONSISTENCY_ANALYSIS, summarize→SUMMARIZE, create_candidate→GENERATE_ENTITY, expand_causal_down→GENERATE_ENTITY, explain_from_causes→CRITICAL_ANALYSIS |
| **Mapeo relation actions** | deepen→EXPAND_ENTITY, suggest_evolution→CONTINUITY_QUESTION, suggest_scene→GENERATE_ENTITY, detect_contradiction→CONSISTENCY_ANALYSIS, suggest_secret_clue→CONTINUITY_QUESTION, create_candidate→GENERATE_RELATION |
| **Mapeo graph actions** | suggest_missing_nodes→GENERATE_ENTITY, suggest_missing_relations→SUGGEST_RELATIONS, detect_isolated_zones→CRITICAL_ANALYSIS, detect_inconsistencies→CONSISTENCY_ANALYSIS, suggest_emergent_plots→CONTINUITY_QUESTION, describe_tree→SUMMARIZE |
| **Formato salida** | `AIResponse` → candidatos `Candidate` (via CandidateService) o previews según action_type |
| **Proveedor** | `create_provider()` → `.invoke()` |
| **creative_brief** | Solo indirecto (via `AuthorizedContext.project_config_snapshot.creative_brief`) |
| **branch_creative_context** | **NO** |
| **Riesgos** | El prompt es genérico y pierde contexto rico. `provider.invoke()` usa el prompt genérico de `_build_prompt()` en OpenAICompatibleProvider: `"[{mode}] instruction. Context: {context}."`. El SimulatedAIProvider retorna respuestas fijas sin entender el contexto. La información de creative_brief/branch_creative_context se pierde. |
| **Recomendación** | **WRAP** — estas rutas deberían migrar a `.chat()` con prompts ricos como las rutas 2-5, o recibir un builder de prompt dedicado. |

---

### Ruta 9-11: OrchestratorService (invoke / generate_candidates / improvise)

| Campo | Detalle |
|-------|---------|
| **Nombre** | Orchestrator invoke / generate_candidates / improvise |
| **Archivos** | `packages/application/orchestrator_service.py` |
| **Función de entrada** | `OrchestratorService.invoke()`, `.generate_candidates()`, `.improvise()` |
| **Prompt** | `AIOperation.prompt_hint` (texto libre) — no hay system prompt rico |
| **Mecanismo** | Construye `AuthorizedContext` simple → `AIOperation` → `provider.invoke()` |
| **invoke()** | Retorna `AIResponse` directamente |
| **generate_candidates()** | invoke() + crea Source IA + crea Candidates + registra history |
| **improvise()** | Usa `AIMode.GENERATE_ENTITY`, parsea líneas del raw_text como name/description/complication/consequence |
| **Proveedor** | `create_provider()` → `.invoke()` |
| **creative_brief** | **NO** — solo genre/tone en `project_config_snapshot` |
| **branch_creative_context** | **NO** |
| **Riesgos** | Sin prompts ricos. `improvise()` asume formato de líneas. `generate_candidates()` puede crear candidates con datos simulados sin sentido. Sin B40. |
| **Recomendación** | **WRAP** — `invoke()` y `generate_candidates()` son legados pre-B31. `improvise()` necesita prompt dedicado. Migrar consumidores a AIContextActionService o AIJobService. |

---

### Ruta 12-14: AnalysisService (Critical / Causal / Consistency)

| Campo | Detalle |
|-------|---------|
| **Nombre** | Analysis Critical / Causal / Consistency |
| **Archivos** | `packages/application/analysis_service.py` |
| **Función de entrada** | `AnalysisService.analyze_entity()`, `.analyze_causal()`, `.analyze_consistency()` |
| **Prompt** | Delegado a `OrchestratorService.invoke()` con `AIMode.CRITICAL_ANALYSIS` / `CAUSAL_ANALYSIS` / `CONSISTENCY_ANALYSIS` |
| **Formato salida** | `CriticalAnalysisResult`, `CausalAnalysisResult`, `ConsistencyAnalysisResult` — parsea candidates de AIResponse |
| **Proveedor** | via OrchestratorService → `create_provider()` → `.invoke()` |
| **creative_brief** | **NO** |
| **branch_creative_context** | **NO** |
| **Riesgos** | Mismos riesgos de OrchestratorService. Los analysis results dependen de candidates con formato específico (type, description, source_id, etc.) que SimulatedAIProvider puede no generar correctamente. |
| **Recomendación** | **WRAP** — migrar a AIContextActionService.run_graph_action() con prompts B40, o integrar con command bar. |

---

### Ruta 15-16: WritingService (expand / critique / rewrite / summarize)

| Campo | Detalle |
|-------|---------|
| **Nombre** | Writing IA assistance |
| **Archivos** | `packages/application/writing_service.py` |
| **Función de entrada** | `WritingService.expand_unit()`, `.critique_unit()`, `.rewrite_unit()`, `.summarize_unit()` |
| **Prompt** | Delegado a `OrchestratorService.invoke()` con AIMode mapeado: writing_expand→EXPAND_ENTITY, writing_critique→CRITICAL_ANALYSIS, writing_rewrite→REWRITE_DESCRIPTION, summarize→SUMMARIZE |
| **Formato salida** | `Candidate` con `CandidateType.SUGERENCIA_IA` (expand/critique/rewrite) o `str` (summarize) |
| **Proveedor** | via OrchestratorService |
| **creative_brief** | **NO** |
| **branch_creative_context** | **NO** |
| **Riesgos** | Sin contexto rico del writing unit. `summarize_unit()` tiene fallback simulado sin IA si no hay orchestrator. |
| **Recomendación** | **WRAP** para expand/critique/rewrite. **LEGACY** para summarize (tiene fallback simulado integrado). |

---

### Ruta 17: Session suggest_material

| Campo | Detalle |
|-------|---------|
| **Nombre** | Session suggest_material |
| **Archivos** | `packages/application/session_service.py` |
| **Función de entrada** | `SessionService.suggest_material()` |
| **Prompt** | **NINGUNO** — no llama al provider. Solo crea un `Candidate` simulado con metadata. |
| **Proveedor** | Ninguno (no usa IA real) |
| **creative_brief** | **NO** |
| **branch_creative_context** | **NO** |
| **Riesgos** | Código muerto — nunca invoca IA, retorna un Candidate vacío. |
| **Recomendación** | **REMOVE_LATER** — no hace nada útil. |

---

### Ruta 18: LiveMode improvise

| Campo | Detalle |
|-------|---------|
| **Nombre** | LiveMode improvise |
| **Archivos** | `packages/application/live_mode_service.py` |
| **Función de entrada** | `LiveModeService.improvise()` |
| **Prompt** | `f"Session: {s.name}. Hint: {hint}"` — texto muy simple pasado a `OrchestratorService.improvise()` |
| **Formato salida** | `dict` con name, description, complication, consequence |
| **Proveedor** | via OrchestratorService |
| **creative_brief** | **NO** |
| **branch_creative_context** | **NO** |
| **Riesgos** | Prompt mínimo sin contexto de proyecto. Resultado de baja calidad sin provider real. |
| **Recomendación** | **WRAP** — necesita prompt rico con contexto de sesión y proyecto. |

---

### Ruta 19-23: Desktop Controllers (AIController / AIContextController)

| Campo | Detalle |
|-------|---------|
| **Nombre** | AIController (generate_entity_candidates, rewrite_entity, test_provider, chat) |
| **Archivos** | `hosts/DesktopHostPySide/controllers/ai_controller.py` |
| **Función de entrada** | `AIController.generate_entity_candidates()`, `.rewrite_entity()`, `.test_provider()`, `.chat()` |
| **Proveedor** | via OrchestratorService (`invoke` / `generate_candidates`) |
| **creative_brief** | **NO** |
| **Recomendación** | **LEGACY** para generate/rewrite (pre-B31). **KEEP** para test_provider y chat. |

| Campo | Detalle |
|-------|---------|
| **Nombre** | AIContextController (chat directo) |
| **Archivos** | `hosts/DesktopHostPySide/controllers/ai_context_controller.py` |
| **Función de entrada** | `AIContextController.chat()` |
| **Proveedor** | `provider.chat()` directo |
| **creative_brief** | **NO** |
| **Recomendación** | **KEEP** — chat genérico útil para features inline de UI. |

---

### Ruta 24-34: CLI ai commands

| Campo | Detalle |
|-------|---------|
| **Nombre** | CLI AI Commands |
| **Archivos** | `packages/ui/cli_ai.py` |
| **Función de entrada** | `handle_ai_command()` |
| **Comandos** | generate-entity, generate-relation, expand, summarize, rewrite, suggest-tags, suggest-relations, continuity, analyze, analyze-group, causal, consistency |
| **Proveedor** | via `OrchestratorService` y `AnalysisService` |
| **creative_brief** | **NO** |
| **branch_creative_context** | **NO** |
| **Riesgos** | Sin B40. Output simulado sin API key. |
| **Recomendación** | **LEGACY** — CLI usa el pipeline viejo de OrchestratorService sin B40. |

---

### Ruta 35-38: UI Workers (QThread)

| Campo | Detalle |
|-------|---------|
| **Nombre** | UI Inline Workers |
| **Archivos** | `hosts/DesktopHostPySide/widgets/node_detail_panel.py`, `tree_detail_panel.py`, `coherence_panel.py` |
| **Workers** | `_AISuggestWorker` (node_text_suggestion), `_AIInlineEditWorker` (chat directo con system prompt inline), `_AINodeActionWorker` (node_action), `_TreeAIWorker` (node_text_suggestion para árboles), `CoherencePanel._run_analysis()` (analyze_coherence/repair_coherence) |
| **Proveedor** | via AIContextController o AIController |
| **creative_brief** | Depende de la ruta subyacente |
| **Recomendación** | **KEEP** — estos son adaptadores QThread, la lógica real está en las rutas 2-5. |

---

## Narrativa Context Builder

### NarrativeContextBuilder
- **Archivo**: `packages/application/narrative_context_builder.py`
- **Rol**: construye diccionarios read-only de contexto para consumidores IA
- **Métodos**: `build_for_entity()`, `build_for_relation()`, `build_for_graph_selection()`, `build_context()`
- **Incluye**: project config, target entity/relation, neighborhood (hasta 12 relaciones/entidades), sessions, campaigns, knowledge (secrets/clues), sources, history, candidates, issues
- **Causal context**: `_causal_context()` — usa `world_layer_causal` para generar resumen de capas causales
- **Creative context**: `_base_context()` incluye `project_creative_brief(project)` y `selected_entity_creative_context()`
- **Tree context**: `_tree_context()` — ancestors, siblings, children, subtree_trees, internal_rules, external_relations
- **Visibilidad**: filtra por audience (gm/player/public), oculta secrets no revelados, clues no entregados

### creative_context.py
- **Archivo**: `packages/application/creative_context.py`
- **`project_creative_brief(project)`**: retorna brief compacto con identity, genre, tone, realism, creative_intent, narrative_engine, poetics, canon, negative_space, taste_memory, ai_preferences
- **`selected_entity_creative_context(project, entity_ids)`**: retorna effective creative config por entidad seleccionada
- **`selected_branch_creative_context(project, entity_ids)`**: retorna effective config solo para contenedores (ramas) con branch_config

---

## Diagrama de Flujo de Proveedores

```
create_provider() / get_provider()
    │
    ├── NARRATIVE_AI_PROVIDER == "openai_compatible"
    │   └── OpenAICompatibleProvider
    │       ├── invoke(operation) → _build_prompt() (GENÉRICO) → HTTP POST → _parse()
    │       │   └── fallback → SimulatedAIProvider.invoke()
    │       └── chat(system, user) → HTTP POST → (text, error)
    │           └── sin key → (None, "Configura API key...")
    │
    └── default → SimulatedAIProvider
        ├── invoke(operation) → respuestas hardcodeadas por AIMode
        └── chat(system, user) → texto determinista según keywords
```

---

## Diagrama de Rutas de Alto Nivel

```
Desktop UI
├── Command Bar → AIJobService.execute_job()
│   └── provider.chat(COMMAND_BAR_SYSTEM_PROMPT_ES, JSON user message)
│       └── B40 completo: creative_brief + branch_creative_context
│
├── Node Detail Panel
│   ├── node_text_suggestion() → AIContextActionService.run_node_text_suggestion()
│   │   └── provider.chat(_ENTITY_TEXT_SYSTEM_PROMPT, _entity_text_user_prompt)
│   ├── chat() directo → AIContextController.chat() → provider.chat()
│   └── node_action() → AIContextActionService.run_node_action() → _run()
│       └── provider.invoke(AIOperation) ← prompt genérico
│
├── Tree Detail Panel
│   ├── node_text_suggestion() → misma ruta que Node Detail
│   └── node_action() → misma ruta que Node Detail
│
├── Relation Detail Panel
│   ├── relation_text_suggestion() → provider.chat(_RELATION_TEXT_SYSTEM_PROMPT)
│   └── relation_action() → provider.invoke(AIOperation) ← prompt genérico
│
├── Coherence Panel
│   ├── analyze_coherence() → provider.chat(_COHERENCE_SYSTEM_PROMPT)
│   └── repair_coherence() → provider.chat(_COHERENCE_REPAIR_SYSTEM_PROMPT)
│
├── Graph Canvas (graph_action)
│   └── AIContextActionService.run_graph_action() → provider.invoke()
│
├── AIController (legacy)
│   ├── generate_entity_candidates() → OrchestratorService.generate_candidates()
│   ├── rewrite_entity() → OrchestratorService.generate_candidates()
│   ├── test_provider() → OrchestratorService.invoke(GENERATE_ENTITY)
│   └── chat() → provider.chat()
│
└── Settings Panel
    └── test_provider() → verifica conectividad

CLI
└── cli_ai handle_ai_command()
    ├── OrchestratorService.generate_candidates() (generate-entity, generate-relation, rewrite, suggest-tags, suggest-relations)
    ├── OrchestratorService.invoke() (expand, summarize, continuity)
    └── AnalysisService (analyze, analyze-group, causal, consistency)
```

---

## Riesgos Globales

1. **Dos pipelines de prompt desacoplados**: `.chat()` con prompts ricos (rutas 1-5) vs `.invoke()` con prompt genérico (rutas 6-11). El pipeline `.invoke()` pierde contexto B40.

2. **OpenAICompatibleProvider._build_prompt()** es extremadamente básico: `"[{mode}] instruction. Context: {context}."`. Esto funciona para SimulatedAIProvider pero produce prompts inútiles para un LLM real.

3. **Sin system prompt en `.invoke()`**: el provider usa solo `role: "user"` con un mensaje único. El system prompt rico solo existe en las rutas `.chat()`.

4. **Coherence Repair parseo incompleto**: el system prompt pide `<PATCH_JSON>` pero no hay extractor que lo parsee y aplique.

5. **Command Bar system prompt solo ES**: no hay versión EN, a diferencia de las rutas contextuales.

6. **CLI sin B40**: todos los comandos CLI usan el pipeline viejo sin creative_brief.

7. **Session suggest_material**: código muerto que no invoca IA.

8. **Improvise prompt mínimo**: un solo string `Session: {name}. Hint: {hint}` sin contexto de proyecto.

---

## Recomendaciones por Prioridad

1. **WRAP rutas invoke() → chat()**: Las rutas 6-8 (node/relation/graph actions via invoke) deberían migrar a `.chat()` con prompts dedicados similares a las rutas 2-5.

2. **Implementar PATCH_JSON extractor**: La ruta 5 (coherence repair) necesita un parser de `<PATCH_JSON>...</PATCH_JSON>` para poder aplicar reparaciones.

3. **WRAP OrchestratorService**: Rutas 9-11 deberían recibir builders de prompt o migrar sus consumidores a AIContextActionService.

4. **WRAP AnalysisService**: Rutas 12-14 deberían usar AIContextActionService con prompts B40.

5. **Eliminar Session suggest_material**: Ruta 17 es código muerto.

6. **Command Bar EN prompt**: Agregar `_EN` variant del system prompt para proyectos en inglés.

7. **CLI B40**: Los comandos CLI deberían integrar creative_brief en su contexto.
