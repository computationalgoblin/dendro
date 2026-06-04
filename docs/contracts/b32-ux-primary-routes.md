# B32 — Contrato de rutas UX principales

Estado: vigente tras B32-DEBT.

## Principio

La UI normal debe presentar una ruta principal por intención de producto. Las rutas técnicas pueden existir para soporte, pruebas, migración o modo avanzado, pero no deben competir visualmente con la ruta principal.

## Rutas principales

| Intención | Ruta principal normal | Ruta secundaria/técnica | Visibilidad normal |
|---|---|---|---|
| Crear entidad | Creación → Taller narrativo/Grafo → Panel de entidad | CorpusView tabla | Visible solo ruta principal |
| Editar entidad | Click nodo en grafo → NodeDetailPanel | CorpusView tabla | Visible solo ruta principal |
| Crear relación | Grafo → RelationCreatePanel / interacción visual | RelationView tabla | Visible solo ruta principal |
| Editar relación | Click relación → RelationDetailPanel | RelationView tabla | Visible solo ruta principal |
| Revisar IA candidata | Panel Sugerencias / Importación documental | CandidateView tabla | Visible como tarjetas; tabla solo avanzado |
| Importar documento | Importación documental → staging/revisión | SourceView/tabla técnica | Visible solo staging limpio |
| Guardar/cargar proyecto | Panel Proyecto | acciones internas/controladores | Visible en panel Proyecto |

## Reglas

- No mostrar `Corpus técnico`, `Relaciones técnicas` ni `Candidatos técnicos` en modo normal.
- No mostrar IDs, JSON, schema, fallback IA ni rutas técnicas en Home o superficie principal.
- `Diagnóstico` no aparece en UI normal hasta que exista contrato funcional validado.
- Las tablas técnicas se conservan solo como soporte avanzado o pruebas.
- Galería y Sesión no bloquean B33; permanecen later hasta que Creación sea estable.
