# KNOWN_ISSUES — Deuda y bugs conocidos (BETA baseline)

Última actualización: 2026-06-10 — Cierre de exploración.

## Bugs activos (validación Windows 2026-06-07)

| ID | Descripción | Severidad |
|----|-------------|-----------|
| BUG-B34-PANEL | Rama no abre panel de detalle | Alta |
| BUG-B34-BADGE | Badge de miembros flota al colapsar | Media |
| BUG-B34-RELINT | No se puede relacionar nodo interno con su rama | Alta |
| BUG-B34-CYCLE | Prevención de ciclos sin enforcement real | Alta |
| BUG-B35-REPAIR | Reparación coherencia no persiste | Alta |
| BUG-B36-WB | Toggle Worldbuilding no propaga al canvas | Alta |
| BUG-B36-TYPO | worldbuilding_enabled vs worldbuilding_active | Alta |
| BUG-B37-FOCUS | Focus vecindad filtra ancestros contenedores | Media |
| BUG-B37-CAM | Cámara tras operaciones | Baja |
| BUG-B38-ERROR | Error provider poco prominente en UI | Baja |

Todos tienen fix en WSL. Sin validación Windows.

## Deuda técnica

Ver `docs/product/product_debt_map.md` para el detalle completo.

Prioridades BETA: DC-026/027/028 (import), DC-033/034 (timeline), DC-035 (IA provider), DC-045 (AnalysisService tests), DC-034-01..04 (layout árboles B34).
