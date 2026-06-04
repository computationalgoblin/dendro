# B32 — Feature triage

Objetivo: separar lo imprescindible del ruido antes de añadir nuevas features.

## Criterios

- CORE: imprescindible para la experiencia Dendro actual o para persistencia/canon.
- SUPPORT: infraestructura útil, debe existir pero no dominar la UI normal.
- LATER: funcionalidad válida, pero no prioritaria para estabilizar Creación.
- HIDE: implementado o parcial, pero debe ocultarse de la UI normal.
- REMOVE: candidato a eliminar tras auditoría de imports/migraciones.
- UNKNOWN: requiere prueba visual/funcional o decisión de producto.

## Clasificación por funcionalidad

| Funcionalidad | Clasificación | Visible normal | Motivo | Decisión B32 |
|---|---:|---:|---|---|
| Proyecto: crear/abrir/guardar/cargar | CORE | Sí | Base de persistencia y flujo de trabajo. | Mantener como panel Proyecto; rutas duplicadas deben apuntar a una acción única. |
| Preferencias app/IA | SUPPORT | Configuración | Necesario, pero no es contenido del proyecto. | Mantener en Configuración; persistir localmente; no mostrar API key. |
| Home inmersiva | CORE | Sí | Primera impresión y navegación. | Mantener; debe reaccionar a tipo de proyecto. |
| Creación/grafo principal | CORE | Sí | Centro del producto y MVP B33. | Prioridad máxima. |
| Crear nodo visual | CORE | Sí | Mínimo de Creación. | B33. |
| Editar nodo en drawer | CORE | Sí | Mínimo de Creación. | B33. |
| IA inline de nodo | CORE | Sí | Asistencia sin canonizar. | Mantener; no candidatos/nodos. |
| Crear relación visual | CORE | Sí | Completa grafo narrativo. | B33. |
| Editar relación en drawer | CORE | Sí | Necesario para grafo usable. | B33. |
| IA inline de relación | CORE | Sí | Paridad con nodo. | B33. |
| Árbol/contenedor semántico | CORE futuro | Sí cuando B34 | Agrupación narrativa central para contexto jerárquico. | B34 tras estabilizar Creación. |
| TreeMeta/custom_metadata | SUPPORT | No crudo | Implementación actual de árbol. | Mantener; validar contrato antes de ampliar. |
| Meter nodos en árboles | CORE futuro | Sí | Necesario para B34. | Priorizar después de B33. |
| IA con contexto de árbol | CORE futuro | Sí | Diferenciador Dendro. | B34/B35. |
| Coherencia de subgrafo | LATER/CORE futuro | Sí cuando estable | Útil tras grafo y árboles. | B35. |
| Worldbuilding por capas causales | LATER | Solo si activo | Importante, pero no antes de grafo/árboles. | B36. |
| Galería | LATER/UNKNOWN | Dudoso | Puede duplicar corpus/grafo si no está clara. | No avanzar hasta B37. |
| Sesión/campaña | LATER | Solo campaña | Potente pero no base de Creación. | B38; ocultar si proyecto no es campaña. |
| Live mode/post-sesión | LATER | Solo campaña | Complejidad alta. | B38. |
| Corpus técnico | HIDE | No | Duplica grafo/lista de entidades; tono administrativo. | Ocultar en modo normal; mantener avanzado. |
| RelationView tabular | HIDE | No | Duplica relación visual; tabla técnica. | Avanzado/admin. |
| CandidateView tabular | SUPPORT/HIDE | Parcial | Revisión necesaria, pero tabla técnica duplica import/IA. | Convertir a tarjetas o avanzado. |
| Importación documental | SUPPORT | Sí, simple | Necesaria como entrada, no como canon directo. | Mantener “Importar material”; revisión por candidatos. |
| ImportCandidate basket | SUPPORT | No directo | Staging de importación. | No mostrar como modelo separado al usuario. |
| Candidate global | CORE/SUPPORT | Sí como revisión | Evita canonización directa de IA/import. | Mantener bandeja de revisión clara. |
| StructuredIssue | SUPPORT | No normal | Incidencias/reparación. | Mantener en diagnóstico/QA/avanzado. |
| Issue legacy | HIDE/REMOVE futuro | No | Modelo legacy convive con StructuredIssue. | No exponer; evaluar eliminación con migración. |
| Diagnóstico/log | SUPPORT/HIDE | No | Útil para soporte, ruido en experiencia. | Configuración/avanzado. |
| Modo avanzado | SUPPORT | Toggle config | Necesario para agentes/usuarios técnicos. | Mantener oculto en Configuración. |
| Frameworks narrativos | LATER/SUPPORT | No normal | Útiles, pero no core UX inicial. | Avanzado o módulo futuro. |
| Timeline | LATER/SUPPORT | No prioridad | Útil para escritura, no para B33. | Posponer. |
| Writing units | LATER/SUPPORT | No prioridad | Puede integrarse con novela, pero no antes de Creación. | Posponer. |
| Sources/history | SUPPORT | No crudo | Trazabilidad obligatoria pero técnica. | Ocultar crudo; mostrar procedencia legible cuando toque. |
| Custom types/fields | SUPPORT/HIDE | No normal | Potente pero técnico. | Avanzado. |
| Domains/layers UI | LATER/SUPPORT | Solo worldbuilding | Worldbuilding depende de proyecto. | Ocultar si worldbuilding off. |
| ProjectStore CRUD legacy | HIDE/REMOVE futuro | No | Duplicado de services. | No usar en rutas nuevas. |
| Scripts B30/B27 smokes | SUPPORT | No | Históricos, no cubren B32. | Mantener; crear nuevos al estabilizar MVP. |

## Decisiones de producto fijadas para seguir

1. La ruta principal de Creación es el grafo, no CorpusView ni tablas.
2. Una sugerencia IA inline nunca crea nodos, relaciones ni candidatos globales.
3. Candidatos globales solo aparecen cuando la acción sea “sugerir entidad/relación” o importación/revisión.
4. Árboles se tratan como agrupadores semánticos; no carpetas técnicas.
5. Sesión solo debe aparecer si el tipo de proyecto incluye campaña.
6. Capas/worldbuilding solo deben aparecer si `worldbuilding_active` está activo.
7. Diagnóstico, JSON, IDs, metadata cruda, tablas admin y logs quedan fuera del modo normal.
