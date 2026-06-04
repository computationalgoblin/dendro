# B32 — Product debt map

Estado tras B32-DEBT: actualizado 2026-06-04.

## P0 — bloquea uso

No queda P0 conocido dentro del alcance validado localmente.

Histórico resuelto durante B32-DEBT:

- pytest no disponible en WSL: resuelto instalando dependencias dev y validando arquitectura.
- contratos estáticos de `TreeDetailPanel`: resuelto con `membershipChanged`, métodos mínimos y campos reales `source_id/target_id`.
- IA inline con riesgo de fallback a candidatos: protegido por contrato/test estático.

## P1 — rompe UX principal

No queda P1 conocido dentro del alcance validado localmente.

Histórico resuelto/mitigado:

- Superficie normal con rutas técnicas: tests actualizados para proteger que no reaparezcan `Corpus técnico`, `Relaciones técnicas`, `Candidatos técnicos` como copy normal.
- Importación mezclando detalle técnico en normal: test cubre normal limpio y avanzado técnico.
- Provider simulado devolviendo texto genérico inglés de rewrite: eliminado.

## P2 — incómodo pero usable

- Validación visual Windows pendiente.
- Galería necesita definición de producto antes de inversión visual.
- Sesión/campaña necesita visibilidad gobernada por tipo de proyecto.
- Worldbuilding por capas debe esperar a contrato de árboles/contexto estable.

## P3 — mejora futura

- Refinar copy de todos los módulos later.
- Añadir pruebas visuales automatizadas si el entorno lo permite.
- Reducir más dependencias entre vistas legacy y workspaces.

## Funcionalidades ocultas o avanzadas

- CorpusView tabular.
- RelationView tabular.
- CandidateView técnica.
- SourceView.
- FrameworkView.
- LayerView cuando `worldbuilding_active=false`.
- IDs, JSON, schema y logs técnicos.

## Funcionalidades eliminables candidatas

No eliminar todavía. Mantener ocultas/avanzadas hasta estabilizar B33-B34 y confirmar que no hacen falta para migración/QA.

## Decisiones pendientes

1. Definir producto de Galería.
2. Definir cuándo se muestra Sesión según tipo de proyecto.
3. Definir contrato persistente final de árboles y membresía.
4. Definir worldbuilding por capas causales después de árboles.
