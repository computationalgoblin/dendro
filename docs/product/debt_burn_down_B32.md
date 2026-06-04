# B32-DEBT — Plan de quema de deuda

Este documento convierte el mapa de deuda B32 en tickets ejecutables antes de avanzar con B33/B34.

## Orden obligatorio

1. `B32-DEBT-T00` — Congelar avance y regularizar working tree.
2. `B32-DEBT-T01` — Restaurar validación mínima y entorno de tests.
3. `B32-DEBT-T02` — Regularizar TreeDetailPanel y relaciones de árbol.
4. `B32-DEBT-T03` — Reducir superficie visible normal de la UI.
5. `B32-DEBT-T04` — Unificar rutas UX de entidad, relación, candidatos e importación.
6. `B32-DEBT-T05` — Separar contratos de IA inline, candidatos, importación e incidencias.
7. `B32-DEBT-T06` — Cerrar deuda P2 visible y copy incoherente.
8. `B32-DEBT-T07` — Consolidar mapa final de deuda y roadmap desbloqueado.

## Regla de avance

No se empieza B33/B34 hasta que B32-DEBT-T07 esté cerrado.

## Tickets de árboles B32 existentes

Los tickets `B32-T01`..`B32-T05` quedan congelados hasta cerrar B32-DEBT. La deuda detectada en `TreeDetailPanel` se regulariza en `B32-DEBT-T02`; después se decide si B34 absorbe o reemplaza el B32 original de árboles.
