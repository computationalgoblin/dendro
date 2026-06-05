# B38 — Smoke Windows: Command Bar IA y UI de Creación

Estado: pendiente de validación visual Windows nativa por el usuario.

## Preparación

1. Abrir el proyecto en Windows nativo.
2. Ejecutar la aplicación de escritorio:
   `python -m hosts.DesktopHostPySide.main`
3. Abrir un proyecto con Creación disponible.
4. Entrar en Creación.

## Smoke T01 — Top bar persistente

1. Confirmar que las acciones principales aparecen arriba.
2. Confirmar que ya no existe la barra inferior antigua de botones.
3. Confirmar que los botones principales no dependen de hover.
4. Confirmar que no aparecen IDs ni JSON en modo normal.

Esperado:
- Barra superior visible.
- Acciones creativas a la izquierda.
- Herramientas de gestión/vista a la derecha.

## Smoke T02 — Panel persistente de capas

1. Activar Worldbuilding en Proyecto.
2. En Creación, pulsar el botón `Capas`.
3. Confirmar que se abre el panel izquierdo.
4. Confirmar que permanece abierto sin hover.
5. Pulsar una capa.
6. Confirmar que el grafo filtra/enfoca esa capa.
7. Volver a pulsar la misma capa o `Ver todas`.
8. Confirmar que el filtro se limpia.
9. Desactivar Worldbuilding.
10. Confirmar que el botón/panel de capas se oculta.

Esperado:
- Panel visible por botón persistente.
- Contadores por capa legibles.
- Sin IDs/JSON.

## Smoke T03 — Command bar IA inferior

1. Confirmar que abajo aparece la barra de prompt de Dendro.
2. Escribir: `Créame tres personajes para empezar esta historia`.
3. Pulsar Enter o botón `Enviar`.
4. Confirmar que la UI no se bloquea.
5. Confirmar progreso/estado discreto del job.
6. Confirmar que se abre panel de resultado revisable.

Esperado:
- Job no bloqueante.
- Resultado en panel interno, no ventana externa.
- Ningún nodo aparece automáticamente en el grafo.

## Smoke T04 — Resultado a bandeja de sugerencias

1. En el panel de resultado, pulsar `Enviar a sugerencias`.
2. Confirmar que se abre la bandeja de sugerencias.
3. Confirmar que aparecen candidatos pendientes.
4. Aceptar un candidato.
5. Confirmar que solo entonces se crea la entidad en canon.
6. Rechazar otro candidato.
7. Confirmar que no se crea entidad rechazada.

Esperado:
- Prompt → job → resultado → candidatos → aceptar/rechazar.
- Sin canonización automática.

## Smoke T05 — Jobs MVP

Probar prompts:

1. `Créame tres personajes`
   - Esperado: candidatos de entidad.
2. `Crea un sistema metafísico`
   - Con Worldbuilding OFF: árbol/contenedor candidato.
   - Con Worldbuilding ON: expansión worldbuilding candidata.
3. `Revisa todo el grafo y proponme mejoras`
   - Esperado: informe/sugerencia IA revisable.
4. Seleccionar dos nodos y ejecutar `Propón relaciones`
   - Esperado: relación candidata con endpoints reales.

## Validaciones técnicas asociadas

Ejecutadas en WSL/offscreen durante implementación:

- `python -m compileall hosts/DesktopHostPySide packages tests -q`
- `QT_QPA_PLATFORM=offscreen python -m pytest tests/application/test_b38_ai_jobs.py tests/desktop/test_b38_command_bar_jobs.py -q`
- `python scripts/run_all_tests.py --suites arch desktop infra sanity b33 b34 b35 b36 b37 b38`

Validación final pendiente:
- prueba visual Windows nativa por el usuario.
