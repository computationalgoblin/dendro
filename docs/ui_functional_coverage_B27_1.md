# UI Functional Coverage B27.1

**Fecha:** 2026-06-01
**Fuente:** AST scan de `packages/application`, `packages/ui`, `hosts/DesktopHostPySide`

---

## 1. Resumen ejecutivo

| Métrica | Valor |
|---------|-------|
| Servicios detectados | 30 clases de servicio |
| Métodos públicos en servicios | ~370 |
| Módulos CLI | 25 |
| Desktop UI controllers | 5 (project, entity, relation, candidate, session) |
| Desktop UI métodos expuestos | 11 (de ~370 totales) |
| Desktop UI views | 8 pantallas |
| Desktop UI TODOs/placeholders | 9 |
| Funciones expuestas en Desktop UI | ~5% de los métodos de servicio |
| Funciones CLI sin Desktop UI | ~95% |
| Riesgos principales | Live mode con hardcoded IDs, accept sin CandidateService real, import sin ImportService |

---

## 2. Desktop UI actual — pantalla por pantalla

### dashboard_view.py
- Servicio: ProjectService (via ProjectController)
- Acciones reales: open (QFileDialog), create (QFileDialog + save), counts (getattr)
- Placeholders: ninguno
- Riesgo: bajo
- Próximo: añadir refresh automático al cambiar de proyecto

### corpus_view.py
- Servicio: EntityService (via EntityController)
- Acciones reales: list (tabla con filtros texto/tipo/canon), get (detalle), create (diálogo name+type), update (name+brief_description)
- Acciones faltantes: archive, restore, filter by domain/layer/tag, search, sort, custom fields, extended description
- Placeholders: ninguno
- Riesgo: bajo
- Próximo: añadir archive/restore, filtros avanzados

### relation_view.py
- Servicio: RelationService (via RelationController)
- Acciones reales: list (tabla source→type→target), create (diálogo con selectores entity+type)
- Acciones faltantes: filter by type/canon/visibility, archive, update, custom fields
- Placeholders: ninguno
- Riesgo: bajo
- Próximo: añadir filtros y archive

### candidate_view.py
- Servicio: CandidateService (via CandidateController)
- Acciones reales: list (tabla), detalle (proposed_data, metadata, source_id, confidence), accept, reject
- Acciones faltantes: accept_with_changes, postpone, merge, convert, archive, filter by state/type/source
- Placeholders: ninguno
- Riesgo: **medio** — accept/reject usa CandidateController pero CandidateService puede no estar inyectado correctamente en todos los flujos
- Próximo: verificar integración CandidateService real en todos los flujos (post-session, import)

### issues_history_view.py
- Servicio: Project (issues) + HistoryService
- Acciones reales: list issues (tabla type/severity/description/affected), list history entries (timestamp/event/description)
- Acciones faltantes: resolve/close issues, filter issues by severity/type, filter history by object/entity
- Placeholders: ninguno
- Riesgo: bajo
- Próximo: añadir resolve/close

### session_view.py
- Servicio: SessionService (via SessionController)
- Acciones reales: list (tabla name/state/campaign), create (diálogo name+campaign_id)
- Acciones faltantes: show, edit, duplicate, scene management, link clue/secret/faction/clock/entity, summary, check, suggest
- Placeholders: ninguno
- Riesgo: bajo — pero session_view solo expone create/list, toda la gestión de escenas y links está en LivePostView
- Próximo: añadir edit/duplicate/show básico

### live_post_view.py
- Servicio: LiveModeService + PostSessionService (via SessionController)
- Acciones reales: activate, quick_note, create_provisional_entity, mark_clue_delivered (hardcoded ID), improvise, prepare_post, close_session, convert_to_candidates, create_session_source, generate_seeds
- Acciones con TODO: player_decision, event, consequence (sin diálogo de texto), secret_reveal (sin selector), post_accept/reject (sin CandidateService real)
- Acciones faltantes: query npcs/locations/secrets/clues/factions/clocks, provisional relations, link entity, proper clue/secret selectors
- Placeholders: 6 (note, decide, event, consequence, clue selector, secret selector)
- Riesgo: **alto** — live mode usa "any_clue" hardcoded, secret_reveal sin parámetros, improvise sin contexto real
- Próximo: P0 — añadir diálogos de texto y selectores reales de clue/secret

### import_export_view.py
- Servicio: ExportService + Project.import_baskets
- Acciones reales: export_all (gm/player/public), export_entity (selector local), export_session (selector local), list_baskets
- Acciones con TODO: import file (selector existe pero no llama ImportService), import accept (no implementado)
- Acciones faltantes: import_document real, basket review, accept/reject import candidates, export campaign report
- Placeholders: 2 (import file integration, import accept)
- Riesgo: **medio** — export funciona con datos reales, import solo muestra baskets sin poder aceptar
- Próximo: P0 — integrar ImportService real

---

## 3. Matriz global por módulo

| Módulo | Servicio | CLI | Desktop UI | Estado UI | Prioridad |
|--------|----------|-----|------------|-----------|-----------|
| **Project** | create/open/save/close/info/schema | ✅ Completo | ✅ open/create/save | ✅ UI completa | — |
| **Entities** | list/get/create/update/archive/filter/search/sort | ✅ Completo | ✅ list/create/update | 🟡 Parcial (sin archive/filter avanzado) | P1 |
| **Relations** | list/create/update/archive/filter | ✅ Completo | ✅ list/create | 🟡 Parcial (sin archive/filter) | P1 |
| **Candidates** | list/accept/reject/postpone/merge/convert | ✅ Completo | ✅ list/accept/reject | 🟡 Parcial (sin postpone/merge) | P0 |
| **Issues** | list/get/resolve/validate | ✅ Completo | ✅ list (solo lectura) | 🟡 Parcial (sin resolve) | P2 |
| **History** | record/get_history | ✅ Completo | ✅ list (recent) | ✅ UI completa | — |
| **Sources** | create/list/link/get | ✅ Completo | ❌ | ❌ No expuesto | P2 |
| **Graph** | build/stats/path/neighborhood | ✅ Completo | ❌ | ❌ No expuesto | B28 |
| **Frameworks** | create/list/toggle/associate/coverage | ✅ Completo | ❌ | ❌ No expuesto | P2 |
| **AI/Orch.** | generate/expand/summarize/improvise | ✅ Completo | 🟡 improvise (parcial) | 🟡 Parcial | P1 |
| **Import** | document/basket/accept/reject/edit/merge | ✅ Completo | 🟠 import file/list (TODO) | 🟠 Placeholder | P0 |
| **Timeline** | create/list/order/check | ✅ Completo | ❌ | ❌ No expuesto | P2 |
| **Writing** | create/list/tree/expand/link/check | ✅ Completo | ❌ | ❌ No expuesto | P2 |
| **Campaign** | create/list/overview/player/pc/clock | ✅ Completo | ❌ | ❌ No expuesto | P1 |
| **Secrets** | create/reveal/knowledge/detect | ✅ Completo | ❌ | ❌ No expuesto | P1 |
| **Clues** | create/deliver/link/pending | ✅ Completo | ❌ | ❌ No expuesto | P1 |
| **Factions** | create/ally/enemy/front/clock/detect | ✅ Completo | ❌ | ❌ No expuesto | P1 |
| **Sessions** | create/duplicate/scene/link/summary | ✅ Completo | 🟡 create/list | 🟡 Parcial (sin scenes/links) | P0 |
| **Live Mode** | open/query/note/entity/reveal/improvise | ✅ Completo | 🟡 parcial + 🟠 6 TODOs | 🟠 Placeholder/TODO | P0 |
| **Post-session** | close/summary/candidates/source/seeds | ✅ Completo | 🟡 parcial (sin idempotencia visible) | 🟡 Parcial | P0 |
| **Export** | all/entity/session/campaign gm/player/public | ✅ Completo | ✅ export all/entity/session | ✅ UI completa | — |
| **Domains/Layers** | create/list/show | ✅ Completo | ❌ | ❌ No expuesto | P2 |
| **Custom Types** | create/list/delete entity/relation/field types | ✅ Completo | ❌ | ❌ No expuesto | P3 |
| **Config** | get/set/update avanzada | ✅ Completo | ❌ | ❌ No expuesto | P3 |

---

## 4. Huecos P0/P1 para que la UI sea usable sin CLI

### P0 — Bloqueantes de usabilidad (5 items)
| Gap | Impacto | Ticket |
|-----|---------|--------|
| Import real (ImportService) | Sin import, el flujo documental no funciona en UI | B27.2-T01 |
| Live mode usable (diálogos, selectores clue/secret) | Live mode actual usa IDs hardcoded | B27.2-T02 |
| Session scenes + links en UI | Session sin scenes/links no es usable | B27.2-T03 |
| Post-session candidates reales (idempotencia) | Post-session sin CandidateService real no cierra el ciclo | B27.2-T04 |
| CandidateService integración real (accept/reject/post-session) | Candidates sin servicio real no aplican cambios | B27.2-T05 |

### P1 — Paridad básica (7 items)
| Gap | Impacto | Ticket |
|-----|---------|--------|
| Campaign view | Sin campaña, no hay contexto para sesiones/facciones | B27.2-T06 |
| Secrets + Clues view | Sin secretos/pistas, el ciclo conocimiento está roto | B27.2-T06 |
| Factions + Fronts view | Sin facciones, el ciclo campaña está incompleto | B27.2-T06 |
| Entity archive/filter avanzado | Sin archive, el corpus se vuelve inmanejable | B27.2-T07 |
| Relation filter/archive | Sin filtros, las relaciones son difíciles de navegar | B27.2-T07 |
| AI provider info en UI | Sin saber qué provider está activo, el usuario no confía | B27.2-T08 |
| Writing view básica | Sin writing, el módulo narrativo no tiene UI | B27.2-T09 |

---

## 5. Recomendación final

```text
B27.1 requiere fixes antes de B28? → Sí. Live mode e import tienen placeholders críticos.

Conviene crear B27.2 antes de B28? → Sí. B27.2 debe cerrar los 5 gaps P0.

Qué puede esperar a B28? → Graph, Frameworks, Timeline, Writing, Domains/Layers.

Qué debe ir a B29? → Custom types, Config avanzada, optimizaciones.

Orden recomendado:
B27.2-T01..T05 (P0: import, live, sessions, post-session, candidates) → 1 sprint
B27.2-T06..T09 (P1: campaign, secrets, factions, archive, AI info, writing) → 1 sprint
B28 (Graph + frameworks + timeline UI) → 1 sprint
B29 (Rendimiento + partial_order + get_tree) → 1 sprint
B30 (Cierre + docs) → 1 sprint
```
