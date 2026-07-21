# Roadmap — Dendro / Narrative Architect (BETA)

Última actualización: 2026-07-21 — cierre técnico de la fase BETA.

## Fase completada: Exploración (B1–B44)

Fundación → dominio → persistencia → CLI → Desktop UI → IA → worldbuilding →
coherencia → árboles → anillos → física de grafo. 44 bloques, 30+ suites.

## Fase actual: BETA — implementación COMPLETA, pendiente de smokes de usuario

Estado operativo autoritativo: [.kanban/KANBAN.md](../../.kanban/KANBAN.md).
Épicas entregadas (todas con tests en verde):

- **BETA1** — recorte de runtime (A), estabilidad IA/trazabilidad (D), UX (F/UX,
  plegada), datación temporal (J), cronología (CRON), estabilidad Qt (K),
  escalabilidad y navegación a escala (L01/L02), auditoría (AUDIT). Fases C/G/I
  canceladas por decisión de producto (2026-07-03).
- **BETA2** — Foco+Jardín (FOCO/JARDIN), retratos (IMG), memoria narrativa (MEM)
  reencuadrada a **wiki+índice navegable** (WIKI, método Karpathy), calendario por
  eras (CAL), modo Play (PLAY), subhitos (SUB), hover (HOVER), pulido (PULIDO/UI2),
  cleanup de paneles, y **propuestas estructurales** (STRUCT: ring_move,
  ascending_exception, branch_move, ring_create/merge — completa 2026-07-21).
- **Limpieza post-WIKI (2026-07-21)**: purga física del legacy IA (command bar,
  RAG léxico, acciones contextuales), deuda técnica a **cero**
  ([product_debt_map.md](product_debt_map.md)), capas sin allowlist, y baseline
  de tests **en verde total** (core 2140 + arch 11 + ui).

Esquema de persistencia: **v39** (fuente de verdad: `packages/persistence/schema.py`).

## Puerta de cierre de BETA

La única puerta restante es la **batería de smokes manuales del usuario** en
plataforma real: ver [beta_closure_checklist.md](beta_closure_checklist.md)
(sustituto ligero de la fase G de validación, cancelada). Lo que falle en un
smoke vuelve como ticket de remediación al tablero.

## Deuda activa

**Cero deuda abierta** al cierre técnico — ver [product_debt_map.md](product_debt_map.md)
(única fuente; el antiguo `KNOWN_ISSUES.md` nunca llegó a existir).

## Post-beta (sin comprometer)

Candidatos anotados en tickets/cierres: refinar el tipo semántico de las
excepciones ascendentes vía IA, altas/bajas incrementales del canvas (L01
follow-up), gestión de imágenes más allá de retratos (FOCO), pin manual de zona.
