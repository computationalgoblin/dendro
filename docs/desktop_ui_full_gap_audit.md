# Desktop UI — Full gap audit B27.3

**Fecha:** 2026-06-01
**Método:** AST cross-reference: 339 service methods vs 29 UI controller methods (8%)

---

## 1. Servicios con CERO cobertura UI

Estos servicios existen en código, tienen CLI, pero NO tienen ningún controller ni vista en DesktopHost.

| Servicio | Métodos | CLI | Impacto |
|----------|---------|-----|---------|
| **CampaignService** | 20 | `campaign create/list/show/edit/overview/player/pc/clock` | 🔴 Crítico — campañas inaccesibles |
| **SecretsService** | 25 | `secret create/list/show/edit/reveal/hidden/knowledge/detect` | 🔴 Crítico — secretos/pistas inaccesibles |
| **FactionService** | 28 | `faction create/list/show/edit/ally/enemy/front/clock/detect` | 🔴 Crítico — facciones inaccesibles |
| **FrameworkService** | 18 | `framework list/show/create/edit/toggle/coverage/duplicate` | 🟡 Frameworks sin UI |
| **TimelineService** | 10 | `timeline list/show/create/edit/check` | 🟡 Timeline sin UI |
| **GraphService** | 4 | `graph summary/entity/path/neighborhood` | 🟡 Grafo sin UI |
| **SourceService** | 8 | `source create/list/show` | 🟡 Sources sin UI |
| **WorldLayerService** | 6 | Sin CLI directa | 🟡 Layers sin UI |
| **AnalysisService** | 3 | Sin CLI directa | 🟡 Análisis sin UI |
| **HistoryService** | 5 | `history entity/recent` | 🟡 History sin controller |
| **OrchestratorService** | 4 | `ai generate/suggest/improvise` | 🟡 IA sin controller |
| **IssueService** | 10 | `issue list/show/validate` | 🟡 Issues sin controller |
| **PostSessionService** | 7 | `session close/post-candidates/summary` | 🔴 Post-sesión sin controller |
| **LiveModeService** | 15 | `session live open/note/entity/clue/secret/improvise/done` | 🔴 Live mode sin controller |
| **QueryService** | 10 | Sin CLI directa | 🟡 Búsqueda sin UI |
| **TextSearchService** | 4 | Sin CLI directa | 🟡 Búsqueda sin UI |
| **AdvancedConfigService** | 4 | `config get/set` | 🟡 Config sin UI |

## 2. Servicios con cobertura PARCIAL

| Servicio | UI controller | Expuesto | Faltante |
|----------|---------------|----------|----------|
| **EntityService** | EntityController | `list_all, get, create, update` (4/35) | archive, restore, filter by type/canon/visibility/domain/layer/tag, search, sort, change canon/visibility, custom fields |
| **RelationService** | RelationController | `list_all, create` (2/24) | update, archive, filter by type/canon/visibility, get incoming/outgoing, neighborhood, layers, custom fields |
| **CandidateService** | CandidateController | `list_all, accept, reject` (3/15) | create, update, accept_with_changes, postpone, merge, convert, archive, filter by entity/source/state |
| **SessionService** | SessionController | `list_all, create` (2/18) | update, duplicate, scenes (add/remove/reorder), link clue/secret/faction/clock/entity, summary, check, suggest |
| **ImportService** | ImportController | `import_document, list_baskets, get_basket, accept, reject, edit, merge` (7/18) | partial import, detect duplicates/contradictions, generate candidates |
| **ExportService** | Ninguno (inline en import_export_view) | `export_all, export_entity, export_session` (3/6) | campaign report, relation profile, proper no-leak validation |
| **WritingService** | WritingController | `list_all, create` (2/20) | update, archive, reorder, reparent, tree, link entity, coverage, expand/summarize/critique/rewrite |
| **ProjectService** | ProjectController | `open, create, save` (3/8) | save_as, close, validate, config get/set |

## 3. Funciones UI que acceden a datos SIN controller

Estas vistas acceden directamente a `project` (sin pasar por servicio). Son frágiles y rompen la arquitectura:

| Vista | Accede directamente a | Debería usar |
|-------|----------------------|-------------|
| `campaign_view.py` | `self.ctrl._proj` | CampaignController |
| `secrets_clues (en campaign_view.py)` | `self.ctrl._proj.secrets, .clues` | SecretsService |
| `faction_front (en campaign_view.py)` | `self.ctrl._proj.factions, .fronts` | FactionService |
| `issues_history_view.py` | `self.controller._proj.issues, .history_entries` | IssueService, HistoryService |
| `live_post_view.py` | `self.sc.ls` inline | LiveModeController |
| `corpus_view.py` | `self.ec` (parcial) | EntityController (ya lo usa) |
| `relation_view.py` | `self.rc.ps.active_project.entities` | EntityController |

## 4. Ranking de gaps por criticidad

### 🔴 P0 — Bloquea operación normal del producto (6 gaps)

| Gap | Qué falta | Ticket |
|-----|-----------|--------|
| Campañas no gestionables | CampaignView solo tabla; sin create funcional desde UI | B27.3-T03 |
| Secretos/pistas no gestionables | SecretsCluesView solo tabla; no create/reveal/deliver desde UI | B27.3-T06 |
| Facciones no gestionables | FactionFrontView solo tabla; no flujo entity→faction desde UI | B27.3-T04 |
| Post-sesión sin controller | LivePostView.Post tab accede a servicios sin controller | B27.3-T08 |
| Live mode sin controller | LivePostView.Live tab accede a LiveModeService sin controller | B27.3-T07 |
| Candidate avanzado | Solo accept/reject; sin postpone/merge/convert/filters | B27.3-T05 |

### 🟡 P1 — Funcionalidad importante ausente (9 gaps)

| Gap | Qué falta | Ticket |
|-----|-----------|--------|
| Writing avanzado | Solo list/create; falta tree real, link, expand, coverage | B27.3-T09 |
| Timeline | Sin vista en absoluto | B27.3-T10 |
| Frameworks | Sin vista en absoluto | B27.3-T11 |
| Graph | Sin vista (B28) | B28 |
| Sources | Sin vista | B27.3-T12 |
| Layers/Domains | Sin vista | B27.3-T13 |
| Entity archive/filtros avanzados | Archive implementado, filtros avanzados no | B27.3-T14 |
| Relation archive/filtros avanzados | Sin implementar | B27.3-T15 |
| Config avanzada | Sin vista | B27.3-T16 |

### ⚪ P2 — Mejoras (4 gaps)

| Gap | Qué falta |
|-----|-----------|
| TextSearch | Sin UI |
| QueryService | Sin controller |
| AnalysisService | Sin UI |
| CustomTypeService | Sin UI |

---

## 5. Resumen ejecutivo

```
339 métodos de servicio
 29 expuestos en controllers (8%)
 ~35 accedidos directamente desde vistas (sin controller)
 ~60 funcionalidades CLI sin equivalente UI
  6 gaps P0 (bloquean operación normal)
  9 gaps P1 (funcionalidad importante ausente)
  4 gaps P2 (mejoras)
 14 servicios sin controller propio
```
