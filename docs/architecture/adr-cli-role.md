# ADR: Rol de la CLI técnica en narrative-architect

**Estado:** Aceptado
**Fecha:** 2026-05-30
**Contexto:** El proyecto ha construido 15 bloques con CLI como interfaz principal.

## Decisión

La CLI actual es **UI técnica de validación** (nivel 1 del contrato §9). No es UI de producto final.

- **Propósito:** validar contratos internos, servicios de aplicación, persistencia, trazabilidad y flujos manuales de prueba.
- **Consume:** servicios de aplicación (`ProjectService`, `EntityService`, `RelationService`, `IssueService`, `CandidateService`, `FrameworkService`, `OrchestratorService`, `GraphService`, `QueryService`, etc.)
- **No accede a:** `ProjectStore`, archivos JSON, mutación directa de colecciones.
- **Futuro:** la UI final (web/escritorio/TUI avanzada) reutilizará los mismos servicios de aplicación.

## Niveles de UI (§9 del contrato)

| Nivel | Definición | Estado actual |
|-------|-----------|---------------|
| 1. CLI técnica | Interfaz de línea de comandos para pruebas, smoke, operación técnica | ✅ Implementado |
| 2. UI provisional | Interfaz mínima operativa antes de la definitiva | ❌ No implementado |
| 3. UI final | Interfaz diseñada para uso continuo del usuario final | ❌ Futuro |

## Requisitos para UI final

- Framework a decidir (web, escritorio, TUI avanzada)
- Debe consumir los servicios de aplicación existentes
- No debe acceder a persistencia directamente
- Debe respetar visibilidad/canon en todas las vistas
- Debe mostrar trazabilidad (fuente, historial) en fichas

## Mapa de funcionalidades → nivel UI

| Funcionalidad | CLI técnica | ¿Necesita UI final? |
|--------------|-------------|---------------------|
| entity CRUD | ✅ | Sí — ficha visual + tabla |
| relation CRUD | ✅ | Sí — panel de relaciones |
| issue list/resolve | ✅ | Sí — panel de incidencias |
| candidate review/accept | ✅ | Sí — bandeja de revisión |
| framework coverage | ✅ | Sí — vista de marcos |
| graph entity/export | ✅ | Sí — grafo interactivo |
| ai generate/summarize | ✅ | Sí — panel IA integrado |
| source list | ✅ | Parcial — panel de fuentes |
| history recent | ✅ | Parcial — timeline |
| custom types | ✅ | Sí — editor de tipos |

## Consecuencias

- Los bloques B16+ pueden seguir usando CLI técnica para validación.
- La UI final se construirá sobre los mismos servicios de aplicación.
- No se requiere migración de datos ni cambio de modelo.
