# ROADMAP — Dendro / Narrative Architect

Última actualización: 2026-06-06

Fuente operativa: este archivo resume el estado de trabajo. No sustituye a:

- `docs/contracts/contrato_fases` como contrato de fases autoritativo para B1-B30.
- Contratos específicos posteriores en `docs/contracts/`.
- Kanban como fuente de ejecución de tickets.
- `docs/cierres/` como evidencia técnica de cierres cuando existe.
- `docs/agents/HANDOFF.md` como traspaso operativo entre agentes.

## Estado actual

| Campo | Valor |
|---|---|
| Fase activa | Post-B43 — sin bloque de implementación autorizado |
| Último bloque implementado | B43 — Migración completa a Prompt Registry |
| Tipo | Espera de decisión / validación / posible hardening documental |
| Fase detallada | `PHASE_CURRENT.md` |
| Rama actual | `feature/B36-T01-causal-layer-contract` |
| Schema | v23 |
| Estado Windows | Validaciones visuales B36-B43 pendientes de Windows nativo |

## Bloques cerrados recientes

| Bloque | Estado | Evidencia |
|---|---|---|
| B30 — Gate/cierre contractual | Cerrado | `docs/cierres/bloque-30-cierre.md` |
| B31 — UX Desktop | Cerrado | `docs/cierres/bloque-31-cierre.md` |
| B32 — Hardening/deuda | Cerrado como estabilización | `docs/contracts/bloque-32-debt-hardening.md`, `docs/product/B32_DEBT_T07_closure.md` |
| B33 — Creación MVP | Cerrado | `docs/cierres/bloque-33-creacion-mvp.md` |
| B34 — Árboles y contexto jerárquico | Cerrado con deuda visual documentada | `docs/cierres/bloque-34-arboles-jerarquicos.md` |
| B35 — Coherencia de subgrafo | Cerrado | `docs/cierres/bloque-35-coherencia-subgrafo.md` |
| B36 — Worldbuilding por capas causales | Aprobado/cerrado documentalmente; Windows visual pendiente | `docs/cierres/bloque-36-cierre.md` |
| B37 — Creación a escala | Aprobado/cerrado documentalmente; Windows visual pendiente | `docs/cierres/bloque-37-cierre.md` |
| B38 — Command bar IA y jobs revisables | Aprobado/cerrado documentalmente; Windows visual pendiente | `docs/cierres/bloque-38-cierre.md` |
| B39 — Modelo visible + control operativo | Aprobado/cerrado documentalmente | `docs/cierres/bloque-39-cierre.md` |
| B40 — Configuración creativa + wizard | Aprobado/cerrado documentalmente; Windows pendiente | `docs/cierres/bloque-40-configuracion-creativa.md` |
| B41 — Milestones causales | Aprobado/cerrado documentalmente; Windows pendiente | `docs/cierres/bloque-41-cierre.md` |
| B42 — Hardening y eficiencia de IA | Aprobado/cerrado documentalmente; Windows pendiente | `docs/cierres/bloque-42-cierre.md` |
| B43 — Prompt Registry migration | Aprobado/cerrado documentalmente; Windows pendiente | `docs/cierres/bloque-43-cierre.md` |

## Situación operativa

No hay un B44 aprobado ni tickets autorizados para nueva funcionalidad. La regla actual sigue siendo:

> Si una idea no cabe en `PHASE_CURRENT.md`, no se implementa ahora: se registra en Kanban, deuda o backlog.

## Próximos gates antes de nuevas features

1. Revisar y, si procede, commitear esta sincronización documental.
2. Validar visualmente en Windows nativo con `docs/pruebas/prueba_visual_guiada_B30_B43.md`.
3. Validar que los cierres documentales B37/B38/B39/B41/B42/B43 creados el 2026-06-06 son aceptados por el usuario.
4. Elegir explícitamente el siguiente bloque desde Kanban/contrato, no desde conversación suelta.
5. Crear tickets Kanban, esperar revisión del usuario y sólo implementar tras aprobación explícita.

## Próximos candidatos de bloque

| Candidato | Condición de entrada |
|---|---|
| Hardening Windows visual B36-B43 | Si la prueba Windows detecta fallos visuales o runtime |
| Revisión de cierres B37/B38/B39/B41/B42/B43 | Si el usuario quiere ajustar el formato o pedir más evidencia antes de B44 |
| B44+ nuevo producto | Sólo con contrato/tickets revisados y aprobación explícita |
| Continuación de Creación/UX | Sólo tras decidir alcance y estado de validación Windows |
| Sesión/campaña Desktop | Sólo cuando Creación esté estable y validada |

## Fuentes relacionadas

- Handoff operativo: `docs/agents/HANDOFF.md`
- Fase activa: `PHASE_CURRENT.md`
- Deuda conocida: `KNOWN_ISSUES.md`
- Decisiones: `docs/adr/`
- Cambios relevantes: `CHANGELOG.md`
- Roadmap histórico de producto: `docs/product/roadmap.md`
- Deuda histórica de producto: `docs/product/product_debt_map.md`
