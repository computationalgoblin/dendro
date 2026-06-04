# B32-DEBT-T07 — Cierre de quema de deuda

Fecha: 2026-06-04
Rama: `feature/B31-immersive-ux`

## Resultado

Bloque B32-DEBT ejecutado completo antes de avanzar a B33/B34.

## Tickets cerrados

| Ticket | Resultado |
|---|---|
| B32-DEBT-T00 | Snapshot del working tree creado y regularización encauzada. |
| B32-DEBT-T01 | pytest restaurado mediante dependencias dev; runner actualizado con `desktop` e `infra`. |
| B32-DEBT-T02 | `TreeDetailPanel` regularizado: señal `membershipChanged`, métodos esperados, uso de `source_id/target_id`. |
| B32-DEBT-T03 | Tests actualizados para proteger Home/Creación limpias y ocultar rutas técnicas en normal. |
| B32-DEBT-T04 | Rutas UX principales documentadas y protegidas por contrato. |
| B32-DEBT-T05 | Límites IA inline/candidatos/importación/incidencias documentados y protegidos por test estático. |
| B32-DEBT-T06 | Copy P2 corregido: árbol/subárbol/descripción/sesión/exportación/documento. |
| B32-DEBT-T07 | Cierre documental, validaciones y roadmap actualizado. |

## Cambios técnicos principales

- `scripts/run_all_tests.py` incluye suites `desktop` e `infra`.
- `tests/desktop/test_b27_5_shell_static.py` deja de exigir labels técnicos visibles y valida la UX actual.
- `tests/desktop/test_import_export_view.py` valida modo normal limpio y modo avanzado técnico.
- `tests/ui/test_b32_ai_boundaries_static.py` protege que IA inline use `node_text_suggestion` y no candidatos.
- `ImportExportView` permite `export_service=None` para pruebas/componentes de importación sin activar export.
- `TreeDetailPanel` usa campos reales de relación (`source_id`, `target_id`) y expone contrato mínimo esperado.
- Provider simulado ya no devuelve `Rewritten description in a different style.`.

## Deuda P0/P1 restante

No queda deuda P0/P1 conocida dentro del alcance B32-DEBT tras las validaciones locales.

## Deuda no resuelta / decisiones pendientes

- Validación visual Windows sigue pendiente: WSL no sustituye prueba manual nativa de PySide en Windows.
- Galería sigue clasificada como `LATER/UNKNOWN` hasta definir su producto.
- Sesión sigue clasificada como `LATER` y debe depender de tipo de proyecto campaña.
- Worldbuilding por capas debe esperar a estabilizar árboles/contexto jerárquico.
- Working tree se regulariza por commit al cierre porque antes de B32-DEBT ya existían cambios acumulados B31/B32.

## Roadmap desbloqueado

1. B33 — Creación MVP estable.
2. B34 — Árboles y contexto jerárquico.
3. B35 — Coherencia de subgrafo.
4. B36 — Worldbuilding por capas causales.
5. B37 — Galería limpia.
6. B38 — Sesión/campaña.

## Validaciones requeridas

- `python -m compileall hosts/DesktopHostPySide packages -q`
- `python -m pytest tests/architecture/ -q`
- `python scripts/run_all_tests.py --suites arch desktop infra sanity`
- prueba visual Windows posterior.
