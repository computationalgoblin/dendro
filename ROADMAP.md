# ROADMAP — Dendro / Narrative Architect

Última actualización: 2026-06-05
Fuente operativa: este archivo resume el estado de trabajo. No sustituye a:

- `docs/contracts/contrato_fases` como contrato de fases autoritativo.
- Kanban como fuente de ejecución de tickets.
- `docs/cierres/` como evidencia técnica de cierres.

## Estado actual

| Campo | Valor |
|---|---|
| Fase activa | B39 — Control operativo del proyecto |
| Tipo | Hardening documental/tooling, sin features narrativas nuevas |
| Contrato | `docs/contracts/bloque-39-contrato.md` |
| Fase detallada | `PHASE_CURRENT.md` |
| Kanban padre | `t_4b60170c` |
| Estado Windows | Validaciones visuales B36/B37/B38 pendientes de Windows nativo |

## Bloques cerrados recientes

| Bloque | Estado | Evidencia |
|---|---|---|
| B33 — Creación MVP | Cerrado | `docs/cierres/bloque-33-creacion-mvp.md` |
| B34 — Árboles y contexto jerárquico | Cerrado con deuda visual documentada | `docs/cierres/bloque-34-arboles-jerarquicos.md` |
| B35 — Coherencia de subgrafo | Cerrado | `docs/cierres/bloque-35-coherencia-subgrafo.md` |
| B36 — Worldbuilding por capas causales | Implementado en WSL; Windows visual pendiente | `docs/cierres/bloque-36-cierre.md` |
| B37 — Creación a escala | Implementado en WSL; Windows visual pendiente | Kanban/cierres del bloque; ver suite `b37` |
| B38 — Command bar IA y jobs revisables | Implementado en WSL; Windows visual pendiente | `docs/validation/b38-command-bar-windows-smoke.md` |

## Bloque activo: B39

Objetivo: reducir caos operativo instalando artefactos livianos y verificables:

- fase activa única,
- roadmap operativo,
- deuda conocida,
- decisiones arquitectónicas,
- changelog por bloques,
- plantillas de trabajo,
- verificación única,
- sanity tests documentales.

Regla central:

> Si una idea no cabe en `PHASE_CURRENT.md`, no se implementa ahora: se registra en Kanban, deuda o backlog.

## Próximos gates antes de nuevas features

1. Cerrar B39 con working tree limpio.
2. Validar smoke Windows de B38:
   - `docs/validation/b38-command-bar-windows-smoke.md`
3. Decidir si las validaciones Windows pendientes B36/B37/B38 bloquean el siguiente bloque de producto.
4. Elegir siguiente bloque explícito desde Kanban/contrato, no desde conversación suelta.

## Próximos candidatos de bloque

| Candidato | Condición de entrada |
|---|---|
| Hardening Windows visual B36-B38 | Si la prueba Windows detecta fallos visuales o runtime |
| Continuación de Creación/UX | Solo tras B39 y decisión explícita de alcance |
| Galería | Solo si el contrato de fase lo vuelve a activar |
| Sesión/campaña Desktop | Solo cuando Creación esté estable y validada |

## Fuentes relacionadas

- Contrato operativo B39: `docs/contracts/bloque-39-contrato.md`
- Fase activa: `PHASE_CURRENT.md`
- Deuda conocida: `KNOWN_ISSUES.md`
- Decisiones: `docs/adr/`
- Cambios relevantes: `CHANGELOG.md`
- Roadmap histórico de producto: `docs/product/roadmap.md`
- Deuda histórica de producto: `docs/product/product_debt_map.md`
