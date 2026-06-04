# Roadmap — Dendro / Narrative Architect

Última actualización: B34 completado.

## Bloques completados

- B01-B24: Fundación, dominio, persistencia, importación, CLI.
- B25-B26: Análisis, importación avanzada.
- B27-B29: Desktop UI, navegación, Grafo.
- B30-B31: UX visual, Home, Creación, Configuración, Proyecto.
- B32-B34: Árboles jerárquicos, pertenencia, contexto IA, z-order/hit-testing.
- **B35: Coherencia de subgrafo.** Análisis, reparación, aceptar/descartar, 17 tests.
- B27: IA provider, escritura asistida.
- B28: CLI robustez, candidates.
- B29-B30: Timeline, robustez general.
- B31: Desktop UI — primera pasada visual (Home, Creación).
- B32: Árboles semánticos — modelo de datos y servicios.
- B33: Grafo interactivo — nodos, edges, drag, selección.
- B34: Árboles jerárquicos — contenedores, collapse, layout, z-order, contexto IA.

## Bloque actual

- **B35**: Coherencia de subgrafo — análisis de consistencia dentro de árboles.
  - Trabaja sobre modelo/servicios/contexto, NO sobre perfección visual del canvas.
  - No rediseña layout (ver DC-034-04).

## Bloques pendientes

- **B36**: Worldbuilding por capas — sistema de capas en Creación cuando worldbuilding activo.
- **B31-UX-FIX-02**: Home + Creación + Configuración/Proyecto como núcleo inmersivo (pausa actual, retomar tras B35).
  - Tipografía máquina de escribir, fondo blanco roto, animaciones zoom.
  - Configuración (abajo izquierda) con Apariencia, IA (chatbot prueba), Avanzado.
  - Proyecto (abajo derecha) con tipo, worldbuilding, género, tono, sistema rol.
  - Visibilidad por tipo de proyecto: campaña → Sesión, novela → sin Sesión.
  - Worldbuilding → capas en Creación, contexto IA.

## Deuda que puede afectar roadmap

| ID | Impacto |
|----|---------|
| DC-034-04 | Pasada graph layout/scene graph futura. No bloquea B35. |
| DC-B28-UI-WIN | Validación Windows Desktop pendiente. |
| DC-045 | AnalysisService sin tests. |

## Orden recomendado

1. B35 — Coherencia de subgrafo (modelo/servicios).
2. B36 — Worldbuilding por capas.
3. B31-UX-FIX-02 — Pulido inmersivo Home/Creación/Config/Proyecto.
4. Pasada graph layout — Resolver DC-034-04.
5. Galería + Sesión — Cuando Home y Creación estén sólidos.
