# CLI → UI Parity Audit B27.3

**Fecha:** 2026-06-01
**Fuente:** AST scan de `packages/ui/cli*.py` vs `hosts/DesktopHostPySide/views/*.py`

## 1. Flujos críticos rotos

| Flujo | CLI | UI | Estado |
|-------|-----|----|--------|
| Crear campaña | `campaign create "X" --system D&D` | Solo tabla, sin botón create | 🔴 ROTO |
| Ver ficha entidad | `entity show <id>` con --extended | Solo tabla + campo texto | 🔴 ROTO |
| Ver ficha relación | `relation show <id>` | Solo tabla sin detail click | 🔴 ROTO |
| Facciones | `faction create --entity <id>` | Entities FACCION no tienen botón "Create faction extension" | 🔴 ROTO |
| Issues | `issue validate` / `secret detect-issues` | Solo tabla lectura, sin run validators | 🔴 ROTO |
| IA real | `ai generate-entity --prompt ...` | Topbar muestra provider pero sin test ni acciones | 🔴 ROTO |
| Session con campaña | `session create "X" --campaign <id>` | Diálogo create no tiene selector de campaña | 🟡 PARCIAL |
| Live queries | `session live npcs/locations/...` | No expuesto en UI | ❌ FALTA |
| Candidate avanzado | `candidate postpone/merge/convert` | No expuesto | 🟡 PARCIAL |
| Import partial | `import partial --characters` | No expuesto | 🟡 PARCIAL |

## 2. Prioridad de fixes

| P0 | Fix |
|----|-----|
| T02 | Entity/Relation detail cards con doble-click, todas las relaciones/issues/history/candidates asociados |
| T03 | Campaign create/edit desde UI + session campaign selector |
| T04 | Faction extension flow: entity FACCION → "Crear extensión de facción" → Faction gestionable |
| T05 | Issues: botón "Run validators" que llama a los servicios existentes |
| T06 | AI: test provider, generate entity, improvise con OrchService real y env vars |
| T07 | Smoke QA Windows |
