# CHANGELOG — Dendro / Narrative Architect

Formato basado en bloques. Este archivo resume cambios relevantes para humanos; no sustituye a `git log`, Kanban ni cierres técnicos.

## 2026-06-05 — B39 Control operativo del proyecto

Planificado/implementado como bloque de hardening documental y tooling mínimo.

Añadido:

- `ROADMAP.md`
- `PHASE_CURRENT.md`
- `KNOWN_ISSUES.md`
- `docs/adr/ADR-001-control-operativo-del-proyecto.md`
- plantillas operativas en `docs/templates/`
- scripts de verificación única `scripts/verify_all.sh` y `scripts/verify_all.ps1`
- sanity tests B39

Objetivo: hacer explícitos fase activa, deuda, gates, decisiones y validación antes de continuar con nuevas features.

## 2026-06-05 — B38 Command bar IA y jobs revisables

Commits relevantes:

- `2c877cf` — contrato UI B38.
- `d6e63a2` — barra superior Creación, panel de capas persistente, command bar IA y contrato AIJob.
- `f2a2cd5` — runner no bloqueante, dispatch, resultados revisables y candidatos.

Estado:

- Implementado y validado en WSL/offscreen.
- Validación visual Windows nativa pendiente.

Cambios clave:

- Command bar IA inferior en Creación.
- Jobs IA in-memory no bloqueantes.
- Resultados pasan a panel/bandeja revisable.
- Nada se canoniza automáticamente.

## 2026-06-04 — B36 Worldbuilding por capas causales

Cierre: `docs/cierres/bloque-36-cierre.md`

Estado:

- Implementado en WSL.
- Validación Windows nativa pendiente.

Cambios clave:

- Vista por capas causales si Worldbuilding ON.
- Asignación de capas en nodos/árboles.
- Relaciones causales.
- Acciones IA descendente/ascendente como sugerencias.
- Coherencia B35 usa contexto causal.

## Bloques recientes previos

| Bloque | Resumen | Evidencia |
|---|---|---|
| B35 | Coherencia de subgrafo, reparación y candidatos | `docs/cierres/bloque-35-coherencia-subgrafo.md` |
| B34 | Árboles jerárquicos y contexto IA | `docs/cierres/bloque-34-arboles-jerarquicos.md` |
| B33 | Creación MVP estable | `docs/cierres/bloque-33-creacion-mvp.md` |
| B31 | UX Desktop | `docs/cierres/bloque-31-cierre.md` |
| B30 | Gate/cierre contractual | `docs/cierres/bloque-30-cierre.md` |

## Regla de mantenimiento

Al cerrar un bloque significativo:

1. Añadir entrada fechada.
2. Enlazar cierre técnico o checklist.
3. Indicar validaciones reales.
4. Indicar deuda/Windows pendiente si aplica.
5. No inventar resultados no ejecutados.
